from typing import Dict, List, Optional, Any, Callable, Deque, Set

import psutil
from pydantic import BaseModel, Field
import logging
from datetime import datetime
import json
import yaml
import uuid
from pathlib import Path
from collections import deque
import asyncio
from contextlib import contextmanager

from pilott.core.task import Task, TaskResult, TaskStatus
from pilott.core.status import AgentStatus


class AgentConfig(BaseModel):
    """Configuration model for agent initialization"""
    role: str
    goal: str
    backstory: Optional[str] = None
    knowledge: List[str] = Field(default_factory=list)
    max_iter: int = Field(default=10, gt=0)
    verbose: bool = False
    allow_delegation: bool = False
    additional_config: Dict[str, Any] = Field(default_factory=dict)
    max_queue_size: int = Field(default=100, gt=0)


class PromptManager:
    """Manages prompts from YAML configuration"""

    def __init__(self):
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict[str, Any]:
        """Load prompts from rules.yaml"""
        try:
            rules_path = Path(__file__).parents[1] / "source/rules.yaml"
            with open(rules_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logging.error(f"Failed to load rules: {str(e)}")
            return {}

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
        self.id = str(uuid.uuid4())
        self.function_calling_llm = function_calling_llm
        self.tools = tools or []
        self.prompt_manager = PromptManager()
        self._locks: Dict[str, asyncio.Lock] = {}

        # Execution state
        self.status = AgentStatus.IDLE
        self.current_task: Optional[Task] = None
        self.step_callback = step_callback
        self.iteration_count = 0

        # History and logging
        self.logger = self._setup_logger()
        self.MAX_HISTORY_SIZE = 100
        self.TASK_TIMEOUT = 300  # 5 minutes
        self.conversation_history: Deque[Dict[str, str]] = deque(maxlen=self.MAX_HISTORY_SIZE)
        self.execution_locks: Dict[str, asyncio.Lock] = {}

        self.tasks: Dict[str, Task] = {}
        self.active_tasks: Set[str] = set()
        self.task_history: Deque[Dict[str, Any]] = deque(maxlen=1000)
        self.task_metrics: Dict[str, int] = {
            "completed": 0,
            "failed": 0,
            "timeout": 0
        }

    @contextmanager
    async def _timeout(self, timeout: float):
        """Context manager for timeout handling"""
        try:
            yield await asyncio.wait_for(asyncio.shield(asyncio.sleep(0)), timeout=timeout)
        except asyncio.TimeoutError:
            raise

    async def execute_task(self, task: Task) -> TaskResult:
        if task.id in self.active_tasks:
            raise ValueError(f"Task {task.id} is already being executed")

        self.status = AgentStatus.BUSY
        self.current_task = task
        self.active_tasks.add(task.id)
        start_time = datetime.now()

        try:
            task_lock = self.execution_locks.setdefault(task.id, asyncio.Lock())
            async with task_lock:
                result = await asyncio.wait_for(
                    self._execute_task_internal(task),
                    timeout=self.TASK_TIMEOUT
                )

                if result.success:
                    self.task_metrics["completed"] += 1
                else:
                    self.task_metrics["failed"] += 1

                return result

        except asyncio.TimeoutError:
            self.task_metrics["timeout"] += 1
            return TaskResult(
                success=False,
                output=None,
                error="Task execution timed out",
                execution_time=(datetime.now() - start_time).total_seconds()
            )
        finally:
            self.active_tasks.discard(task.id)
            self.status = AgentStatus.IDLE
            self.current_task = None
            if task.id in self.execution_locks:
                del self.execution_locks[task.id]

    async def _execute_task_internal(self, task: Task) -> TaskResult:
        """Internal task execution logic with proper lock management"""
        start_time = datetime.now()
        lock_acquired = set()
        try:
            self._validate_task(task)
            analysis = await self._analyze_task(task)
            if not analysis.get("can_execute", True):
                raise ValueError(f"Cannot execute task: {analysis.get('reason')}")
            selected_tools = await self._select_tools(task)

            # Acquire locks in a fixed order to prevent deadlocks
            for tool in sorted(selected_tools.get("selected_tools", [])):
                if tool not in self._locks:
                    self._locks[tool] = asyncio.Lock()
                await self._locks[tool].acquire()
                lock_acquired.add(tool)
            steps_result = await self._execute_steps(task, selected_tools)
            evaluation = await self._evaluate_result(task, steps_result)
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
            execution_time = (datetime.now() - start_time).total_seconds()
            return TaskResult(
                success=False,
                output=None,
                error=str(e),
                execution_time=execution_time
            )
        finally:
            # Release locks in reverse order
            for tool in sorted(lock_acquired, reverse=True):
                if tool in self._locks:
                    self._locks[tool].release()

    async def get_health(self) -> Dict[str, Any]:
        """Get agent health status"""
        return {
            "status": self.status,
            "active_tasks": len(self.active_tasks),
            "total_tasks": len(self.tasks),
            "metrics": self.task_metrics,
            "memory_usage": len(self.conversation_history),
            "locks": {
                task_id: lock.locked()
                for task_id, lock in self.execution_locks.items()
            }
        }

    def _validate_task(self, task: Task) -> bool:
        """Validate task before execution"""
        if not task.description:
            raise ValueError("Task must have a description")
        if task.dependencies:
            for dep_id in task.dependencies:
                if dep_id not in self.tasks:
                    raise ValueError(f"Dependency {dep_id} not found")
                dep_task = self.tasks[dep_id]
                if dep_task.status != TaskStatus.COMPLETED:
                    raise ValueError(f"Dependency {dep_id} not yet completed")
        if not isinstance(task.max_retries, int) or task.max_retries < 0:
            raise ValueError("Task max_retries must be a non-negative integer")
        if task.deadline and not isinstance(task.deadline, datetime):
            raise ValueError("Task deadline must be a datetime object")
        return True

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
        """Execute a single step with proper error handling"""
        tool_name = step.get("tool")
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not available")

        try:
            if step.get("requires_llm", False) and self.function_calling_llm:
                # Use function calling LLM with timeout
                async with self._timeout(60):  # 60-second timeout for LLM calls
                    response = await self.function_calling_llm.generate_response(
                        messages=[{
                            "role": "user",
                            "content": json.dumps(step)
                        }],
                        tools=[{"name": tool_name}]
                    )
                    return response.get("tool_response")
            else:
                # Direct tool execution with timeout
                async with self._timeout(30):  # 30-second timeout for tool execution
                    result = await self._execute_tool(tool_name, step.get("inputs", {}))
                    return {"status": "success", "output": result}

        except asyncio.TimeoutError:
            raise TimeoutError(f"Step execution timed out for tool {tool_name}")
        except Exception as e:
            self.logger.error(f"Step execution failed: {str(e)}")
            raise RuntimeError(f"Tool execution failed: {str(e)}")

    async def _execute_tool(self, tool_name: str, inputs: Dict[str, Any]) -> Any:
        """Execute a tool with proper error handling"""
        tool = self.tools[tool_name]
        try:
            return await tool.execute(**inputs)
        except Exception as e:
            self.logger.error(f"Tool {tool_name} execution failed: {str(e)}")
            raise

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
        """Get response from LLM with error handling"""
        try:
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
            response = await self.llm.generate_response(messages)
            if not response:
                raise ValueError("Empty response from LLM")

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
        """Update conversation history with automatic size management"""
        for message in messages:
            self.conversation_history.append(message)

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
        """Setup logging with proper error handling"""
        logger = logging.getLogger(f"Agent_{self.config.role}")
        if not logger.handlers:
            try:
                handler = logging.StreamHandler()
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                handler.setFormatter(formatter)
                logger.addHandler(handler)
            except Exception as e:
                print(f"Failed to setup logger: {str(e)}")
        logger.setLevel(logging.DEBUG if self.config.verbose else logging.INFO)
        return logger

    async def start(self):
        """Start the agent and its task processor"""
        try:
            self.logger.info(f"Starting agent {self.id}")
            self.status = AgentStatus.IDLE
            self.logger.info(f"Agent {self.id} started successfully")
        except Exception as e:
            self.logger.error(f"Failed to start agent: {str(e)}")
            self.status = AgentStatus.ERROR
            raise

    async def stop(self):
        """Stop the agent and cleanup"""
        try:
            self.logger.info(f"Stopping agent {self.id}")
            self.status = AgentStatus.STOPPED

            # Cancel all running tasks
            for task_id, lock in self.execution_locks.items():
                try:
                    if lock.locked():
                        lock.release()
                except Exception as e:
                    self.logger.error(f"Error releasing lock for task {task_id}: {str(e)}")

            # Clear all state
            self.execution_locks.clear()
            self.conversation_history.clear()
            self.current_task = None
            self.iteration_count = 0

            self.logger.info(f"Agent {self.id} stopped successfully")
        except Exception as e:
            self.logger.error(f"Error stopping agent: {str(e)}")
            self.status = AgentStatus.ERROR
            raise

    async def add_task(self, task: Task) -> None:
        """Add a task to the agent"""
        if task.id in self.tasks:
            raise ValueError(f"Task {task.id} already exists")

        self.tasks[task.id] = task
        self.logger.info(f"Added task {task.id}")

    async def remove_task(self, task_id: str) -> None:
        """Remove a task from the agent"""
        if task_id in self.active_tasks:
            raise ValueError(f"Cannot remove active task {task_id}")

        if task_id in self.tasks:
            del self.tasks[task_id]
            self.logger.info(f"Removed task {task_id}")

    async def cleanup_resources(self):
        """Clean up agent resources safely"""
        try:
            for lock in self._locks.values():
                if lock.locked():
                    lock.release()
            self._locks.clear()
            self.conversation_history.clear()

            # Clean up file handles
            if hasattr(self, 'file_handles'):
                for handle in self.file_handles:
                    try:
                        handle.close()
                    except:
                        pass
                self.file_handles.clear()
        except Exception as e:
            self.logger.error(f"Error cleaning up resources: {str(e)}")

    # async def _analyze_task(self, task: Task) -> Dict[str, Any]:
    #     """Analyze task requirements and resources"""
    #     try:
    #         return {
    #             "can_execute": True,
    #             "required_capabilities": task.required_capabilities,
    #             "estimated_duration": task.estimated_duration or 30,
    #             "complexity": task.complexity,
    #             "resource_requirements": {
    #                 "memory": 0.5,
    #                 "cpu": 0.5
    #             }
    #         }
    #     except Exception as e:
    #         self.logger.error(f"Task analysis failed: {str(e)}")
    #         return {"can_execute": False, "reason": str(e)}

    async def wait_for_tasks(self):
        """Wait for all current tasks to complete"""
        while self.active_tasks:
            await asyncio.sleep(1)

    async def pause_task_acceptance(self):
        """Pause accepting new tasks"""
        self.status = AgentStatus.BUSY

    async def get_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics"""
        return {
            "queue_size": len(self.tasks),
            "active_tasks": len(self.active_tasks),
            "success_rate": self.task_metrics["completed"] /
                            (self.task_metrics["completed"] + self.task_metrics["failed"])
            if (self.task_metrics["completed"] + self.task_metrics["failed"]) > 0
            else 0.0,
            "queue_utilization": len(self.tasks) / self.config.max_queue_size,
            "cpu_usage": psutil.cpu_percent() / 100,
            "memory_usage": psutil.virtual_memory().percent / 100
        }

    async def evaluate_task_suitability(self, task: Dict) -> float:
        """Evaluate how suitable this agent is for a task"""
        try:
            # Check required capabilities
            if "required_capabilities" in task:
                missing_capabilities = set(task["required_capabilities"]) - set(self.config.required_capabilities)
                if missing_capabilities:
                    return 0.0

            # Base suitability score
            score = 0.7

            # Adjust based on task type match
            if "type" in task and hasattr(self, "specializations"):
                if task["type"] in self.specializations:
                    score += 0.2

            # Adjust based on current load
            metrics = await self.get_metrics()
            load_penalty = metrics["queue_utilization"] * 0.3
            score = max(0.0, score - load_penalty)

            return min(1.0, score)

        except Exception as e:
            self.logger.error(f"Error evaluating task suitability: {str(e)}")
            return 0.0

    async def reset(self):
        """Reset agent state"""
        self.status = AgentStatus.IDLE
        self.current_task = None
        self.iteration_count = 0
        self.conversation_history.clear()
        self._locks.clear()
        self.tasks.clear()
        self.active_tasks.clear()
        self.task_metrics = {
            "completed": 0,
            "failed": 0,
            "timeout": 0
        }

    async def determine_strategy(self, task: Task) -> Dict[str, Any]:
        """Determine execution strategy for a task"""
        return {
            "parallel_execution": False,
            "priority_level": task.priority,
            "resource_allocation": {
                "max_agents": 1,
                "time_allocation": 30,
                "tool_requirements": []
            },
            "coordination_needs": [],
            "monitoring_points": [],
            "abort_conditions": []
        }

    async def select_agent(self, task: Task):
        """Select an agent for task execution"""
        try:
            for agent in self.child_agents.values():
                if agent.status != "busy":
                    return agent
            return None
        except Exception as e:
            self.logger.error(f"Agent selection failed: {str(e)}")
            return None

    async def evaluate_result(self, task: Task, result: TaskResult) -> Dict[str, Any]:
        """Evaluate task execution result"""
        return {
            "success": result.success,
            "quality_score": 5,
            "matches_requirements": True,
            "goal_alignment": 5,
            "improvements": [],
            "next_actions": [],
            "reasoning": str(result.error) if not result.success else "Task completed"
        }