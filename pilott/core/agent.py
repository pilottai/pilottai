from typing import Dict, List, Optional, Any, Callable
from pydantic import BaseModel, Field
import asyncio
import logging
from datetime import datetime
import json
import yaml
from pathlib import Path

from pilott.core.task import Task, TaskResult
from pilott.core.status import AgentStatus


class AgentConfig(BaseModel):
    """Configuration model for agent initialization"""
    role: str
    goal: str
    backstory: Optional[str] = None
    knowledge: List[str] = Field(default_factory=list)
    max_iter: int = 10
    verbose: bool = False
    allow_delegation: bool = False
    additional_config: Dict[str, Any] = Field(default_factory=dict)


class PromptManager:
    """Manages prompts from YAML configuration"""

    def __init__(self):
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict[str, Any]:
        """Load prompts from rules.yaml"""
        rules_path = Path(__file__).parent / "rules.yaml"
        with open(rules_path, 'r') as f:
            return yaml.safe_load(f)

    def format_prompt(self, prompt_type: str, **kwargs) -> str:
        """Format a prompt of given type with provided arguments"""
        try:
            template = self.rules['agent'][prompt_type]
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Invalid prompt type or missing key: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error formatting prompt: {str(e)}")


class BaseAgent:
    """LLM-driven agent implementation using structured prompts"""

    def __init__(
            self,
            role: str,
            goal: str,
            backstory: Optional[str] = None,
            knowledge: Optional[List[str]] = None,
            config: Optional[Dict[str, Any]] = None,
            llm: Optional[Any] = None,
            function_calling_llm: Optional[Any] = None,
            max_iter: int = 10,
            verbose: bool = False,
            allow_delegation: bool = False,
            tools: Optional[List[str]] = None,
            step_callback: Optional[Callable] = None
    ):
        if not llm:
            raise ValueError("LLM is required for agent operation")

        # Initialize configuration
        self.config = AgentConfig(
            role=role,
            goal=goal,
            backstory=backstory,
            knowledge=knowledge or [],
            max_iter=max_iter,
            verbose=verbose,
            allow_delegation=allow_delegation,
            additional_config=config or {}
        )

        # Core components
        self.llm = llm
        self.function_calling_llm = function_calling_llm
        self.tools = tools or []
        self.prompt_manager = PromptManager()

        # Execution state
        self.status = AgentStatus.IDLE
        self.current_task: Optional[Task] = None
        self.step_callback = step_callback
        self.iteration_count = 0

        # History and logging
        self.conversation_history: List[Dict[str, str]] = []
        self.logger = self._setup_logger()

    async def execute_task(self, task: Task) -> TaskResult:
        """Execute a task using LLM-driven decision making"""
        self.status = AgentStatus.BUSY
        self.current_task = task
        start_time = datetime.now()

        try:
            # Task analysis
            analysis = await self._analyze_task(task)
            self.logger.info(f"Task analysis completed: {json.dumps(analysis, indent=2)}")

            if not analysis.get("can_execute", True):
                raise ValueError(f"Cannot execute task: {analysis.get('reason')}")

            # Tool selection
            selected_tools = await self._select_tools(task)
            self.logger.info(f"Tools selected: {json.dumps(selected_tools, indent=2)}")

            # Execute steps
            steps_result = await self._execute_steps(task, selected_tools)

            # Evaluate results
            evaluation = await self._evaluate_result(task, steps_result)
            self.logger.info(f"Result evaluation: {json.dumps(evaluation, indent=2)}")

            if not evaluation.get("success", False):
                raise ValueError(f"Task failed: {evaluation.get('reasoning')}")

            execution_time = (datetime.now() - start_time).total_seconds()

            return TaskResult(
                success=True,
                output=steps_result,
                execution_time=execution_time,
                metadata={
                    "analysis": analysis,
                    "tools_used": selected_tools,
                    "evaluation": evaluation,
                    "iterations": self.iteration_count
                }
            )

        except Exception as e:
            self.logger.error(f"Task execution failed: {str(e)}")
            execution_time = (datetime.now() - start_time).total_seconds()
            return TaskResult(
                success=False,
                output=None,
                error=str(e),
                execution_time=execution_time
            )

        finally:
            self.status = AgentStatus.IDLE
            self.current_task = None
            self.iteration_count = 0

    async def _analyze_task(self, task: Task) -> Dict[str, Any]:
        """Analyze task using LLM"""
        prompt = self.prompt_manager.format_prompt(
            "task_analysis",
            role=self.config.role,
            goal=self.config.goal,
            task_description=task.description
        )

        response = await self._get_llm_response(prompt, "task_analysis")
        return self._parse_json_response(response, "task analysis")

    async def _select_tools(self, task: Task) -> Dict[str, Any]:
        """Select tools using LLM"""
        prompt = self.prompt_manager.format_prompt(
            "tool_selection",
            role=self.config.role,
            tools=json.dumps(self.tools),
            task_description=task.description
        )

        response = await self._get_llm_response(prompt, "tool_selection")
        return self._parse_json_response(response, "tool selection")

    async def _execute_steps(self, task: Task, selected_tools: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute task steps with LLM guidance"""
        context = {
            "task": task.dict(),
            "selected_tools": selected_tools,
            "completed_steps": [],
            "current_step": 0
        }

        while self.iteration_count < self.config.max_iter:
            # Get next step
            next_step = await self._determine_next_step(context)

            if next_step.get("task_complete", False):
                break

            # Execute step
            step_result = await self._execute_step(next_step)

            # Update context
            context["completed_steps"].append({
                "step": next_step,
                "result": step_result
            })
            context["current_step"] += 1
            self.iteration_count += 1

            # Execute callback if provided
            if self.step_callback:
                await self._execute_callback(
                    self.step_callback,
                    step=next_step,
                    result=step_result,
                    context=context
                )

        return context["completed_steps"]

    async def _determine_next_step(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Determine next step using LLM"""
        prompt = self.prompt_manager.format_prompt(
            "step_planning",
            task_description=context["task"]["description"],
            completed_steps=json.dumps(context["completed_steps"]),
            available_tools=json.dumps(context["selected_tools"]),
            last_result=json.dumps(context["completed_steps"][-1] if context["completed_steps"] else None)
        )

        response = await self._get_llm_response(prompt, "step_planning")
        return self._parse_json_response(response, "step planning")

    async def _execute_step(self, step: Dict[str, Any]) -> Any:
        """Execute a single step"""
        tool_name = step.get("tool")
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not available")

        if step.get("requires_llm", False) and self.function_calling_llm:
            # Use function calling LLM
            response = await self.function_calling_llm.generate_response(
                messages=[{
                    "role": "user",
                    "content": json.dumps(step)
                }],
                tools=[{"name": tool_name}]
            )
            return response.get("tool_response")
        else:
            # Direct tool execution
            # Implementation depends on your tool execution system
            return {"status": "success", "output": "Tool execution result"}

    async def _evaluate_result(self, task: Task, result: Any) -> Dict[str, Any]:
        """Evaluate task result using LLM"""
        prompt = self.prompt_manager.format_prompt(
            "result_evaluation",
            role=self.config.role,
            goal=self.config.goal,
            task_description=task.description,
            result=json.dumps(result)
        )

        response = await self._get_llm_response(prompt, "result_evaluation")
        return self._parse_json_response(response, "result evaluation")

    async def _get_llm_response(self, prompt: str, context: str) -> str:
        """Get response from LLM with proper system context"""
        messages = [
            {
                "role": "system",
                "content": self.prompt_manager.format_prompt(
                    "system/base",
                    role=self.config.role,
                    goal=self.config.goal,
                    backstory=self.config.backstory or "No specific backstory."
                )
            },
            {"role": "user", "content": prompt}
        ]

        try:
            response = await self.llm.generate_response(messages)
            self._update_conversation_history(messages + [{"role": "assistant", "content": response}])
            return response
        except Exception as e:
            raise RuntimeError(f"Error getting LLM response for {context}: {str(e)}")

    def _parse_json_response(self, response: str, context: str) -> Dict[str, Any]:
        """Parse JSON response from LLM"""
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {context} response: {str(e)}")

    def _update_conversation_history(self, messages: List[Dict[str, str]]):
        """Update conversation history"""
        self.conversation_history.extend(messages)
        # Keep only last 100 messages
        if len(self.conversation_history) > 100:
            self.conversation_history = self.conversation_history[-100:]

    async def _execute_callback(self, callback: Callable, **kwargs):
        """Execute callback with proper async handling"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(**kwargs)
            else:
                await asyncio.to_thread(callback, **kwargs)
        except Exception as e:
            self.logger.error(f"Callback execution failed: {str(e)}")

    def _setup_logger(self) -> logging.Logger:
        """Setup logging for the agent"""
        logger = logging.getLogger(f"Agent_{self.config.role}")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        logger.setLevel(logging.DEBUG if self.config.verbose else logging.INFO)
        return logger