from pilott.core.agent import BaseAgent
from pilott.core.task import Task, TaskResult
from pilott.core.memory import Memory

from typing import Dict, List, Optional, Any, Callable, Set
from pydantic import BaseModel
import asyncio
import logging
from datetime import datetime, timedelta
import json
import yaml
import re
from pathlib import Path
from collections import defaultdict


class ServeConfig(BaseModel):
    name: str = "Pilott"
    memory_enabled: bool = True
    verbose: bool = False
    max_concurrent_tasks: int = 5
    task_timeout: int = 300
    max_queue_size: int = 1000
    cleanup_interval: int = 3600
    task_retention_period: int = 86400
    max_retry_attempts: int = 3


class OrchestratorPromptManager:
    """Manages orchestrator prompts from YAML configuration"""

    def __init__(self):
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict[str, Any]:
        """Load prompts from rules.yaml"""
        rules_path = Path(__file__).parent / "source/rules.yaml"
        with open(rules_path, 'r') as f:
            return yaml.safe_load(f)

    def format_prompt(self, prompt_type: str, **kwargs) -> str:
        """Format prompt with proper template handling"""
        try:
            if prompt_type not in self.rules.get('orchestrator', {}):
                raise ValueError(f"Invalid prompt type: {prompt_type}")

            template = self.rules['orchestrator'][prompt_type]

            # Extract only the top-level parameters from the template
            required_params = set()
            for match in re.finditer(r'\{([^{}\n\r]+)}', template):
                param = match.group(1).strip()
                if param and not any(c in param for c in '{}"\''):
                    required_params.add(param)

            # Check for missing required parameters
            missing_params = required_params - set(kwargs.keys())
            if missing_params:
                raise KeyError(f"Missing required parameters: {missing_params}")

            return template.format(**kwargs)

        except KeyError as e:
            raise ValueError(f"Parameter error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error formatting prompt: {str(e)}")


class Serve:
    """LLM-driven orchestrator using structured prompts"""
    def __init__(
            self,
            agents: List[BaseAgent],
            manager_llm: Optional[Any] = None,
            manager_agent: Optional[BaseAgent] = None,
            memory: bool = True,
            task_callback: Optional[Callable] = None,
            step_callback: Optional[Callable] = None,
            config: Optional[Dict[str, Any]] = None
    ):
        # Validate requirements
        if not agents:
            raise ValueError("At least one agent must be provided")
        if manager_llm and manager_agent:
            raise ValueError("Cannot specify both manager_llm and manager_agent")
        # if not (manager_llm or manager_agent):
        #     raise ValueError("Either manager_llm or manager_agent must be provided")

        # Initialize configuration
        self.config = ServeConfig(**(config or {}))

        # Core components
        self.agents: Dict[str, BaseAgent] = {agent.config.role: agent for agent in agents}
        self.manager_llm = manager_llm
        self.manager_agent = manager_agent
        self.memory = Memory() if memory else None
        self.prompt_manager = OrchestratorPromptManager()

        # Callbacks
        self.task_callback = task_callback
        self.step_callback = step_callback

        # State tracking
        self.tasks: Dict[str, Task] = {}
        self.task_queue = asyncio.Queue(maxsize=self.config.max_queue_size)
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.completed_tasks: Dict[str, TaskResult] = {}
        self.failed_tasks: Dict[str, TaskResult] = {}

        self._task_locks: Dict[str, asyncio.Lock] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._active_agents: Set[str] = set()
        self._shutting_down = False

        # Setup logging
        self.logger = self._setup_logger()

        # Metrics tracking
        self.metrics = defaultdict(int)
        self.last_cleanup = datetime.now()

    async def start(self):
        """Start the orchestrator with enhanced error handling"""
        self.logger.info("Starting Serve orchestrator")
        try:
            # Initialize agents
            for agent in self.agents.values():
                try:
                    await agent.start()
                    self._active_agents.add(agent.config.role)
                except Exception as e:
                    self.logger.error(f"Failed to start agent {agent.config.role}: {str(e)}")
                    continue

            # Start task processor and cleanup
            self.task_processor = asyncio.create_task(self._process_tasks())
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            self.logger.info("Serve orchestrator started successfully")
        except Exception as e:
            self.logger.error(f"Failed to start orchestrator: {str(e)}")
            await self.stop()
            raise

    async def stop(self):
        """Stop orchestrator with graceful cleanup"""
        self.logger.info("Stopping Serve orchestrator")
        self._shutting_down = True

        try:
            # Cancel task processor
            if hasattr(self, 'task_processor'):
                self.task_processor.cancel()
                try:
                    await self.task_processor
                except asyncio.CancelledError:
                    pass

            # Cancel cleanup task
            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass

            # Stop all agents
            for role in list(self._active_agents):
                try:
                    agent = self.agents[role]
                    await agent.stop()
                    self._active_agents.remove(role)
                except Exception as e:
                    self.logger.error(f"Error stopping agent {role}: {str(e)}")

            # Clean up resources
            await self._cleanup_resources()

            self.logger.info("Serve orchestrator stopped successfully")
        except Exception as e:
            self.logger.error(f"Error during orchestrator shutdown: {str(e)}")
            raise

    async def add_task(self, task: Task) -> str:
        """Add task with validation and queueing"""
        if self._shutting_down:
            raise RuntimeError("Orchestrator is shutting down")

        try:
            # Analyze task
            analysis = await self._analyze_task(task)
            self.logger.info(f"Task analysis completed: {json.dumps(analysis, indent=2)}")

            if analysis.get("requires_decomposition", False):
                return await self._handle_complex_task(task, analysis)
            else:
                return await self._handle_simple_task(task)

        except Exception as e:
            self.logger.error(f"Error adding task: {str(e)}")
            raise

    async def _handle_complex_task(self, task: Task, analysis: Dict) -> str:
        """Handle complex task decomposition"""
        try:
            subtasks = await self._decompose_task(task)
            self.logger.info(f"Task decomposed into {len(subtasks)} subtasks")

            tasks = []
            for subtask in subtasks:
                self.tasks[subtask.id] = subtask
                tasks.append(self._queue_task(subtask))

            await asyncio.gather(*tasks)
            return task.id

        except Exception as e:
            self.logger.error(f"Error handling complex task: {str(e)}")
            raise

    async def _handle_simple_task(self, task: Task) -> str:
        """Handle simple task queueing"""
        try:
            self.tasks[task.id] = task
            await self._queue_task(task)
            return task.id
        except asyncio.QueueFull:
            raise RuntimeError("Task queue is full")
        except Exception as e:
            self.logger.error(f"Error handling simple task: {str(e)}")
            raise

    async def _queue_task(self, task: Task):
        """Queue task with overflow protection"""
        try:
            if self.task_queue.qsize() >= self.config.max_queue_size:
                raise RuntimeError("Task queue is full")

            async with asyncio.timeout(5.0):
                await self.task_queue.put(task)
        except asyncio.TimeoutError:
            raise RuntimeError("Task queueing timed out")
        except Exception as e:
            if "Task queue is full" in str(e):
                # Handle overflow
                await self._handle_queue_overflow(task)
            raise

    async def _handle_queue_overflow(self, task: Task):
        """Handle task queue overflow"""
        try:
            # Remove lowest priority tasks if possible
            while (self.task_queue.qsize() >= self.config.max_queue_size and
                   task.priority > self.task_queue._queue[0].priority):
                removed_task = await self.task_queue.get()
                self.failed_tasks[removed_task.id] = TaskResult(
                    success=False,
                    output=None,
                    error="Removed due to queue overflow",
                    execution_time=0
                )

            if self.task_queue.qsize() < self.config.max_queue_size:
                await self.task_queue.put(task)
            else:
                raise RuntimeError("Cannot accommodate task in queue")

        except Exception as e:
            self.logger.error(f"Queue overflow handling failed: {str(e)}")
            raise

    async def _process_tasks(self):
        """Process tasks with improved error handling"""
        while not self._shutting_down:
            try:
                task = await self.task_queue.get()

                # Check if task is still valid
                if task.id not in self.tasks:
                    self.task_queue.task_done()
                    continue

                # Determine execution strategy
                strategy = await self._determine_execution_strategy(task)
                self.logger.info(f"Execution strategy determined: {json.dumps(strategy, indent=2)}")

                if strategy["parallel_execution"] and len(self.running_tasks) < self.config.max_concurrent_tasks:
                    # Execute in parallel
                    self.running_tasks[task.id] = asyncio.create_task(
                        self._execute_task_with_timeout(task)
                    )
                else:
                    # Execute sequentially
                    await self._execute_task_with_timeout(task)

                self.task_queue.task_done()
                self.metrics['processed_tasks'] += 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error processing task: {str(e)}")
                await asyncio.sleep(1)

    async def _execute_task(self, task: Task) -> TaskResult:
        """Execute a single task with LLM-driven agent selection"""
        try:
            agent = await self._select_agent(task)
            if not agent:
                raise ValueError("No suitable agent found for task")

            result = await agent.execute_task(task)

            evaluation = await self._evaluate_result(task, result)
            if not evaluation.get("success", False):
                if evaluation.get("requires_retry", False):
                    result = await self._retry_task(task, evaluation)
                else:
                    raise ValueError(evaluation.get("failure_reason", "Task failed"))

            if self.memory:
                await self._update_memory(task, result)

            if self.task_callback:
                await self._execute_callback(self.task_callback, task=task, result=result, agent=agent)

            return result

        except Exception as e:
            self.logger.error(f"Task execution failed: {str(e)}")
            raise

    async def _execute_task_with_timeout(self, task: Task):
        try:
            async with asyncio.timeout(self.config.task_timeout):
                result = await self._execute_task(task)

                if result.success:
                    self.completed_tasks[task.id] = result
                    self.metrics['successful_tasks'] += 1
                else:
                    self.failed_tasks[task.id] = result
                    self.metrics['failed_tasks'] += 1

                return result

        except asyncio.TimeoutError:
            error_result = TaskResult(
                success=False,
                output=None,
                error="Task execution timed out",
                execution_time=self.config.task_timeout
            )
            self.failed_tasks[task.id] = error_result
            self.metrics['timeout_tasks'] += 1
            raise

    async def _cleanup_loop(self):
        """Periodic cleanup of old tasks and resources"""
        while not self._shutting_down:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self._cleanup_resources()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {str(e)}")

    async def _cleanup_resources(self):
        """Clean up old tasks and resources"""
        try:
            current_time = datetime.now()
            retention_delta = timedelta(seconds=self.config.task_retention_period)

            # Clean up old tasks
            for task_dict in [self.completed_tasks, self.failed_tasks]:
                old_tasks = [
                    task_id for task_id, result in task_dict.items()
                    if current_time - result.completion_time > retention_delta
                ]
                for task_id in old_tasks:
                    del task_dict[task_id]

            # Clean up task locks
            stale_locks = [
                task_id for task_id in self._task_locks
                if task_id not in self.tasks
            ]
            for task_id in stale_locks:
                del self._task_locks[task_id]

            self.last_cleanup = current_time

        except Exception as e:
            self.logger.error(f"Error cleaning up resources: {str(e)}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get orchestrator metrics"""
        return {
            "active_agents": len(self._active_agents),
            "queue_size": self.task_queue.qsize(),
            "running_tasks": len(self.running_tasks),
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "metrics": dict(self.metrics),
            "last_cleanup": self.last_cleanup.isoformat()
        }

    def _validate_response_structure(self, response: Dict, structure: Dict, path: str = "") -> None:
        """Validate response structure recursively"""
        for key, expected_type in structure.items():
            current_path = f"{path}.{key}" if path else key

            if key not in response:
                raise ValueError(f"Missing required field: {current_path}")

            if isinstance(expected_type, dict):
                if not isinstance(response[key], dict):
                    raise ValueError(f"Field {current_path} should be an object")
                self._validate_response_structure(response[key], expected_type, current_path)
            elif isinstance(expected_type, type):
                if not isinstance(response[key], expected_type):
                    raise ValueError(
                        f"Field {current_path} should be of type {expected_type.__name__}"
                    )

    async def _decompose_task(self, task: Task) -> List[Task]:
        try:
            prompt = self.prompt_manager.format_prompt(
                "task_decomposition",
                task_description=task.description
            )

            response = await self._get_llm_response(prompt)
            result = self._parse_json_response(response)

            if not isinstance(result, dict) or "subtasks" not in result:
                raise ValueError("Invalid response structure")

            subtasks = []
            for subtask_data in result["subtasks"]:
                subtask = Task(
                    description=subtask_data["description"],
                    priority=subtask_data.get("priority", task.priority),
                    dependencies=subtask_data.get("dependencies", []),
                    parent_task_id=task.id
                )
                subtasks.append(subtask)

            if not subtasks:
                raise ValueError("No valid subtasks generated")

            return subtasks

        except Exception as e:
            self.logger.error(f"Task decomposition failed: {str(e)}")
            # Return single task if decomposition fails
            return [task]

    async def _determine_execution_strategy(self, task: Task) -> Dict[str, Any]:
        try:
            if self.manager_agent:
                return await self.manager_agent.determine_strategy(task)

            return {
                "parallel_execution": len(self.running_tasks) < self.config.max_concurrent_tasks,
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
        except Exception as e:
            self.logger.error(f"Error determining execution strategy: {str(e)}")
            return {
                "parallel_execution": False,
                "priority_level": 1,
                "resource_allocation": {"max_agents": 1, "time_allocation": 30, "tool_requirements": []},
                "coordination_needs": [],
                "monitoring_points": [],
                "abort_conditions": []
            }

    async def _select_agent(self, task: Task) -> Optional[BaseAgent]:
        try:
            if self.manager_agent:
                return await self.manager_agent.select_agent(task)

            # Default selection if no manager agent
            for agent in self.agents.values():
                if agent.status != "busy":
                    return agent

            return None

        except Exception as e:
            self.logger.error(f"Agent selection failed: {str(e)}")
            if self.agents:
                return next(iter(self.agents.values()))
            return None

    async def _evaluate_result(self, task: Task, result: TaskResult) -> Dict[str, Any]:
        """Evaluate result using manager LLM/agent"""
        try:
            if self.manager_agent:
                return await self.manager_agent.evaluate_result(task, result)

            prompt = self.prompt_manager.format_prompt(
                "result_evaluation",
                task_description=task.description,
                result=json.dumps({
                    "success": result.success,
                    "output": str(result.output),
                    "error": result.error,
                    "execution_time": result.execution_time
                })
            )

            response = await self._get_llm_response(prompt, "result_evaluation")
            return self._parse_json_response(response)

        except Exception as e:
            self.logger.error(f"Result evaluation failed: {str(e)}")
            return {
                "success": result.success,
                "quality_score": 5,
                "matches_requirements": True,
                "goal_alignment": 5,
                "improvements": [],
                "next_actions": [],
                "reasoning": str(result.error) if not result.success else "Task completed"
            }

    async def _retry_task(self, task: Task, retry_strategy: Dict[str, Any]) -> TaskResult:
        """Retry task execution with new strategy"""
        # Modify task based on retry strategy
        modified_task = task.copy(update=retry_strategy.get("task_modifications", {}))

        # Select new agent if specified
        if retry_strategy.get("agent"):
            agent = self.agents.get(retry_strategy["agent"])
            if not agent:
                raise ValueError(f"Retry agent {retry_strategy['agent']} not found")
        else:
            agent = await self._select_agent(modified_task)

        return await agent.execute_task(modified_task)

    async def _get_llm_response(self, prompt: str, context: str = "") -> str:
        """Get response from LLM"""
        try:
            # For orchestrator, we use a simpler prompt without role/goal context
            messages = [
                {"role": "user", "content": prompt}
            ]

            # Use the proper OpenAI interface
            response = await self.manager_llm.apredict(prompt)

            return response

        except Exception as e:
            raise RuntimeError(f"Error getting LLM response for {context}: {str(e)}")

    async def _analyze_task(self, task: Task) -> Dict[str, Any]:
        """Analyze task using manager LLM/agent"""
        try:
            prompt = self.prompt_manager.format_prompt(
                "task_analysis",
                task_description=task.description
            )

            response = await self._get_llm_response(prompt)

            try:
                result = self._parse_json_response(response)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON response from LLM")

            # Validate required fields
            required_fields = {
                "requires_decomposition": bool,
                "complexity": str,
                "estimated_resources": dict
            }

            for field, field_type in required_fields.items():
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")
                if not isinstance(result[field], field_type):
                    raise ValueError(f"Field {field} should be of type {field_type.__name__}")

            return result

        except Exception as e:
            self.logger.error(f"Task analysis failed: {str(e)}")
            raise ValueError(f"Task analysis failed: {str(e)}")

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response with robust error handling"""
        try:
            # First try to find JSON within markdown code blocks
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                # If no code blocks, try to find JSON between curly braces
                start = response.find('{')
                end = response.rfind('}')
                if start != -1 and end != -1:
                    json_str = response[start:end + 1]
                else:
                    json_str = response

            # Clean up the string
            json_str = json_str.strip()

            # Parse the JSON
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                # Try one more time with regex to extract just the JSON object
                import re
                matches = re.findall(r'\{(?:[^{}]|(?R))*}', json_str)
                if matches:
                    return json.loads(matches[0])
                raise e

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing failed. Response: {response}")
            raise ValueError(f"Invalid JSON response: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error parsing response: {str(e)}")
            raise ValueError(f"Failed to parse response: {str(e)}")

    async def _get_function_llm_response(self, messages: List[Dict], tools: List[Dict]) -> Dict:
        """Get function calling LLM response"""
        try:
            # Use the OpenAI function calling interface
            response = await self.function_calling_llm.apredict_messages(
                messages,
                functions=tools
            )
            return response
        except Exception as e:
            raise RuntimeError(f"Error getting function response: {str(e)}")

    async def _update_memory(self, task: Task, result: TaskResult):
        """Update memory with task results"""
        if not self.memory:
            return
        try:
            await self.memory.store({
                "type": "task_execution",
                "task_id": task.id,
                "description": task.description,
                "result": result.model_dump(),
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            self.logger.error(f"Error updating memory: {str(e)}")

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
        """Setup logging for the orchestrator"""
        logger = logging.getLogger(f"Serve_{self.config.name}")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        logger.setLevel(logging.DEBUG if self.config.verbose else logging.INFO)
        return logger

    async def get_result(self, task_id: str) -> Optional[TaskResult]:
        """Get task result"""
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id]
        if task_id in self.failed_tasks:
            return self.failed_tasks[task_id]
        return None