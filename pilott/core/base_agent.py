from typing import Dict, List, Optional, Union
import asyncio
import logging
from datetime import datetime
import uuid

from pilott.core.config import AgentConfig, LLMConfig
from pilott.core.task import Task, TaskResult
from pilott.enums.agent_e import AgentStatus
from pilott.core.memory import Memory
from pilott.engine.llm import LLMHandler
from pilott.tools.tool import Tool
from pilott.knowledge.knowledge import DataManager



class BaseAgent:
    """
    Base agent class for PilottAI framework.
    Handles task execution, tool management, and LLM interactions.
    """

    def __init__(
            self,
            config: AgentConfig,
            llm_config: Optional[LLMConfig] = None,
            tools: Optional[List[Tool]] = None,
            memory_enabled: bool = True
    ):
        # Core configuration
        self.config = config
        self.id = str(uuid.uuid4())
        self.source = Optional[DataManager()]
        self.tasks = Optional[Union[List[Task], Dict[str, Task]]]

        # State management
        self.status = AgentStatus.IDLE
        self.current_task: Optional[Task] = None
        self._task_lock = asyncio.Lock()

        # Components
        self.tools = {tool.name: tool for tool in (tools or [])}
        self.memory = Memory() if memory_enabled else None
        self.llm = LLMHandler(llm_config) if llm_config else None

        # Setup logging
        self.logger = self._setup_logger()

    async def execute_task(self, task: Union[Dict, Task]) -> Optional[TaskResult]:
        """Execute a task with proper handling and monitoring."""
        if isinstance(task, dict):
            task = Task(**task)

        if not self.llm:
            raise ValueError("LLM configuration required for task execution")

        start_time = datetime.now()

        try:
            async with self._task_lock:
                self.status = AgentStatus.BUSY
                self.current_task = task

                # Format task with context
                formatted_task = self._format_task(task)

                # Generate execution plan
                execution_plan = await self._plan_execution(formatted_task)

                # Execute the plan
                result = await self._execute_plan(execution_plan)

                execution_time = (datetime.now() - start_time).total_seconds()

                return TaskResult(
                    success=True,
                    output=result,
                    execution_time=execution_time,
                    metadata={
                        "agent_id": self.id,
                        "role": self.config.role,
                        "plan": execution_plan
                    }
                )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Task execution failed: {str(e)}")
            return TaskResult(
                success=False,
                output=None,
                error=str(e),
                execution_time=execution_time
            )

        finally:
            self.status = AgentStatus.IDLE
            self.current_task = None

    async def _plan_execution(self, task: str) -> Dict:
        """Create execution plan using LLM"""
        messages = [
            {
                "role": "system",
                "content": self._get_system_prompt()
            },
            {
                "role": "user",
                "content": f"Plan execution for task: {task}\n\nAvailable tools: {list(self.tools.keys())}"
            }
        ]

        response = await self.llm.generate_response(messages)

        try:
            # Extract plan from response
            plan = self._parse_json_response(response["content"])
            return plan
        except Exception:
            # Fallback to simple execution
            return {
                "steps": [{
                    "action": "direct_execution",
                    "input": task
                }]
            }

    async def _execute_plan(self, plan: Dict) -> str:
        """Execute the planned steps"""
        results = []

        for step in plan.get("steps", []):
            step_result = await self._execute_step(step)
            results.append(step_result)

            # Store step in memory if enabled
            if self.memory:
                await self.memory.store_semantic(
                    text=f"Step: {step}\nResult: {step_result}",
                    metadata={"type": "execution_step"}
                )

        # Summarize results
        summary = await self._summarize_results(results)
        return summary

    async def _execute_step(self, step: Dict) -> str:
        """Execute a single step of the plan"""
        action = step.get("action")

        if action == "direct_execution":
            # Direct LLM execution
            messages = [
                {
                    "role": "system",
                    "content": self._get_system_prompt()
                },
                {
                    "role": "user",
                    "content": step.get("input")
                }
            ]
            response = await self.llm.generate_response(messages)
            return response["content"]

        elif action in self.tools:
            # Tool execution
            tool = self.tools[action]
            result = await tool.execute(**step.get("parameters", {}))
            return str(result)

        else:
            raise ValueError(f"Unknown action: {action}")

    async def _summarize_results(self, results: List[str]) -> str:
        """Summarize execution results using LLM"""
        messages = [
            {
                "role": "system",
                "content": self._get_system_prompt()
            },
            {
                "role": "user",
                "content": f"Summarize these execution results:\n{results}"
            }
        ]

        response = await self.llm.generate_response(messages)
        return response["content"]

    def _get_system_prompt(self) -> str:
        """Get the system prompt for this agent"""
        return f"""You are an AI agent with:
        Role: {self.config.role}
        Goal: {self.config.goal}
        Backstory: {self.config.backstory or 'No specific backstory.'}

        Make decisions and take actions based on your role and goal."""

    def _format_task(self, task: Task) -> str:
        """Format task with context"""
        task_text = task.description

        if task.context:
            try:
                task_text = task_text.format(**task.context)
            except KeyError as e:
                self.logger.warning(f"Missing context key: {e}")

        return task_text

    def _parse_json_response(self, response: str) -> Dict:
        """Parse JSON response from LLM"""
        try:
            # First try to extract JSON from markdown code blocks
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                json_str = response

            return eval(json_str)  # Using eval for more forgiving parsing

        except Exception as e:
            self.logger.error(f"Failed to parse JSON response: {str(e)}")
            return {}

    async def evaluate_task_suitability(self, task: Dict) -> float:
        """Evaluate how suitable this agent is for a task"""
        try:
            # Base suitability score
            score = 0.7

            if "required_capabilities" in task:
                missing = set(task["required_capabilities"]) - set(self.config.required_capabilities)
                if missing:
                    return 0.0

            # Adjust based on task type match
            if "type" in task and hasattr(self, "specializations"):
                if task["type"] in self.specializations:
                    score += 0.2

            # Adjust based on current load
            if self.status == AgentStatus.BUSY:
                score -= 0.3

            return min(1.0, score)

        except Exception as e:
            self.logger.error(f"Error evaluating suitability: {str(e)}")
            return 0.0

    async def start(self):
        """Start the agent"""
        try:
            self.status = AgentStatus.IDLE

            # Store agent start in memory if enabled
            if self.memory:
                await self.memory.store_semantic(
                    text=f"Agent {self.config.role} started",
                    metadata={
                        "type": "status_change",
                        "status": "started",
                        "agent_id": self.id
                    },
                    tags={"status_change", "agent_start"}
                )

            self.logger.info(f"Agent {self.id} started")

        except Exception as e:
            self.logger.error(f"Failed to start agent: {str(e)}")
            self.status = AgentStatus.ERROR
            raise

    async def stop(self):
        """Stop the agent"""
        try:
            self.status = AgentStatus.STOPPED

            # Store agent stop in memory if enabled
            if self.memory:
                await self.memory.store_semantic(
                    text=f"Agent {self.config.role} stopped",
                    metadata={
                        "type": "status_change",
                        "status": "stopped",
                        "agent_id": self.id
                    },
                    tags={"status_change", "agent_stop"}
                )

            self.logger.info(f"Agent {self.id} stopped")

        except Exception as e:
            self.logger.error(f"Failed to stop agent: {str(e)}")
            raise

    def _setup_logger(self) -> logging.Logger:
        """Setup agent logging"""
        logger = logging.getLogger(f"Agent_{self.config.role}_{self.id}")

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        logger.setLevel(logging.DEBUG if self.config.verbose else logging.INFO)
        return logger
