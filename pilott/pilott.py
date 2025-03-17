import asyncio
import logging
from typing import Dict, List, Optional, Any, Union

from pydantic import BaseModel

from pilott.agent import ActionAgent, MasterAgent, SuperAgent
from pilott.core.base_agent import BaseAgent
from pilott.core.config import AgentConfig, LLMConfig
from pilott.core.memory import Memory
from pilott.core.task import Task, TaskResult
from pilott.enums.process_e import ProcessType
from pilott.enums.task_e import TaskPriority
from pilott.tools.tool import Tool


class ServeConfig(BaseModel):
    """Configuration for Serve orchestrator"""
    name: str = "Pilott"
    process_type: ProcessType = ProcessType.SEQUENTIAL
    memory_enabled: bool = True
    verbose: bool = False
    max_concurrent_tasks: int = 5
    task_timeout: int = 300
    max_queue_size: int = 1000


class Pilott:
    """
    Main orchestrator for PilottAI framework.
    Handles agent management, task execution, and system lifecycle.
    """

    def __init__(
            self,
            name: str = "PilottAI",
            config: Optional[Dict] = None,
            llm_config: Optional[Union[Dict, LLMConfig]] = None
    ):
        # Initialize configuration
        self.config = ServeConfig(**{"name": name, **(config or {})})
        self.llm_config = llm_config

        # Core components
        self.agents: Dict[str, BaseAgent] = {}
        self.tasks: Dict[str, Task] = {}
        self.memory = Memory() if self.config.memory_enabled else None

        # Task management
        self._task_queue = asyncio.Queue(maxsize=self.config.max_queue_size)
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._completed_tasks: Dict[str, TaskResult] = {}

        # Agent Config
        self.master_agent: Optional[MasterAgent] = None
        self.super_agents: List[SuperAgent] = []
        self.action_agents: List[ActionAgent] = []

        # State management
        self._started = False
        self._shutting_down = False
        self._execution_lock = asyncio.Lock()

        # Setup logging
        self.logger = self._setup_logger()

    async def add_agent(
            self,
            role: str,
            goal: str,
            backstory: Optional[str] = None,
            tools: Optional[List[Tool]] = None,
            llm_config: Optional[Union[Dict, LLMConfig]] = None,
            verbose: bool = False
    ) -> BaseAgent:
        """
        Add a new agent to the system.

        Args:
            role: The role/type of the agent
            goal: The agent's primary goal/objective
            backstory: Optional background story for the agent
            tools: List of tool names the agent can use
            llm_config: Optional specific LLM config for this agent
            verbose: Enable detailed logging for this agent

        Returns:
            BaseAgent: The created agent instance
        """
        try:
            config = AgentConfig(
                role=role,
                goal=goal,
                description=f"Agent for {role}",
                backstory=backstory,
                tools=tools or [],
                verbose=verbose
            )

            agent = BaseAgent(
                config=config,
                llm_config=llm_config or self.llm_config
            )

            self.agents[role] = agent
            self.logger.info(f"Added agent: {role}")

            # Start agent if system is running
            if self._started:
                await agent.start()

            return agent

        except Exception as e:
            self.logger.error(f"Failed to add agent {role}: {str(e)}")
            raise

    async def create_task(
            self,
            description: str,
            agent_role: Optional[str] = None,
            priority: Union[TaskPriority, str] = TaskPriority.MEDIUM,
            context: Optional[Dict] = None
    ) -> Task:
        """
        Create a new task.

        Args:
            description: Task description
            agent_role: Optional specific agent role to handle the task
            priority: Task priority (TaskPriority enum or string)
            context: Optional context dictionary

        Returns:
            Task: Created task instance
        """
        try:
            # Convert string priority to enum if needed
            if isinstance(priority, str):
                try:
                    priority = TaskPriority(priority.lower())
                except ValueError:
                    raise ValueError(
                        f"Invalid priority '{priority}'. Must be one of: "
                        f"{', '.join(p.value for p in TaskPriority)}"
                    )

            task = Task(
                description=description,
                priority=priority,
                context=context or {},
                agent_id=agent_role
            )

            self.tasks[task.id] = task
            return task

        except Exception as e:
            self.logger.error(f"Failed to create task: {str(e)}")
            raise

    async def execute(self, tasks: List[dict[str, Any]]) -> List[TaskResult] | None:
        """
        Execute a list of tasks.

        Args:
            tasks: List of tasks to execute

        Returns:
            List[TaskResult]: Results of task execution
        """
        if not self._started:
            await self.start()

        try:
            processed_tasks = []
            for task in tasks:
                if isinstance(task, dict):
                    task = Task(**task)
                processed_tasks.append(task)

            if self.config.process_type == ProcessType.PARALLEL:
                return await self._execute_parallel(processed_tasks)
            elif self.config.process_type == ProcessType.SEQUENTIAL:
                return await self._execute_sequential(processed_tasks)
            elif self.config.process_type == ProcessType.HIERARCHICAL:
                return await self._execute_hierarchical(processed_tasks)
        except Exception as e:
            self.logger.error(f"Task execution failed: {str(e)}")
            raise

    async def start(self):
        """Start the Serve orchestrator"""
        if self._started:
            return

        try:
            # Start all agents
            for agent in self.agents.values():
                await agent.start()

            self._started = True
            self.logger.info("PilottAI Serve started")

        except Exception as e:
            self._started = False
            self.logger.error(f"Failed to start Serve: {str(e)}")
            raise

    async def stop(self):
        """Stop the Serve orchestrator"""
        if not self._started:
            return

        try:
            self._shutting_down = True

            # Stop all running tasks
            for task in self._running_tasks.values():
                task.cancel()

            # Stop all agents
            for agent in self.agents.values():
                await agent.stop()

            self._started = False
            self._shutting_down = False
            self.logger.info("PilottAI Serve stopped")

        except Exception as e:
            self.logger.error(f"Failed to stop Serve: {str(e)}")
            raise

    async def _execute_sequential(self, tasks: List[Task]) -> List[TaskResult]:
        """Execute tasks sequentially"""
        results = []
        for task in tasks:
            try:
                result = await self._execute_single_task(task)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Task execution failed: {str(e)}")
                results.append(TaskResult(
                    success=False,
                    output=None,
                    error=str(e),
                    execution_time=0.0
                ))
        return results

    async def _execute_parallel(self, tasks: List[Task]) -> List[TaskResult]:
        """Execute tasks in parallel"""
        return await asyncio.gather(
            *[self._execute_single_task(task) for task in tasks],
            return_exceptions=True
        )

    async def _execute_hierarchical(self, tasks: List[Task]) -> List[TaskResult]:
        pass

    async def _execute_single_task(self, task: Task) -> TaskResult:
        """Execute a single task"""
        try:
            # Get appropriate agent
            agent = await self._get_agent_for_task(task)
            if not agent:
                raise ValueError(f"No suitable agent found for task: {task.description}")

            # Start task execution
            await task.mark_started()

            # Execute task with timeout
            async with asyncio.timeout(self.config.task_timeout):
                result = await agent.execute_task(task)

            # Complete task
            await task.mark_completed(result)
            return result

        except asyncio.TimeoutError:
            error_result = TaskResult(
                success=False,
                output=None,
                error=f"Task execution timed out after {self.config.task_timeout} seconds",
                execution_time=self.config.task_timeout
            )
            await task.mark_completed(error_result)
            return error_result

        except Exception as e:
            error_result = TaskResult(
                success=False,
                output=None,
                error=str(e),
                execution_time=0.0
            )
            await task.mark_completed(error_result)
            return error_result

    async def _get_agent_for_task(self, task: Task) -> Optional[BaseAgent]:
        """Get appropriate agent for task"""
        if task.agent and task.agent in self.agents:
            return task.agent
        elif task.agent_id and task.agent_id in self.agents:
            return self.agents[task.agent_id]

        # Find best agent based on task requirements
        best_agent = None
        best_score = -1

        for agent in self.agents.values():
            if agent.status != "busy":
                score = await agent.evaluate_task_suitability(task.model_dump())
                if score > best_score:
                    best_score = score
                    best_agent = agent

        return best_agent

    async def delegate(self, agents: List[BaseAgent], parallel: bool = False) -> List[TaskResult]:
        if not self._started:
            await self.start()

        try:
            if parallel:
                return await self._execute_agents_parallel(agents)
            return await self._execute_agents_sequential(agents)

        except Exception as e:
            self.logger.error(f"Agent-based execution failed: {str(e)}")
            raise

    async def _execute_agents_sequential(self, agents: List[BaseAgent]) -> List[TaskResult]:
        """Execute tasks through agents sequentially."""
        all_results = []

        for agent in agents:

            for task in agent.tasks:
                try:
                    await task.mark_started()
                    result = await agent.execute_task(task)
                    await task.mark_completed(result)
                    all_results.append(result)
                except Exception as e:
                    self.logger.error(f"Task execution failed on agent {agent.id}: {str(e)}")
                    error_result = TaskResult(
                        success=False,
                        output=None,
                        error=str(e),
                        execution_time=0.0
                    )
                    await task.mark_completed(error_result)
                    all_results.append(error_result)

        return all_results

    async def _execute_agents_parallel(self, agents: List[BaseAgent]) -> List[TaskResult]:
        """Execute tasks through agents in parallel."""
        all_results = []

        async def process_agent_tasks(agent_id, tasks):
            agent = self.agents[agent_id]
            results = []
            self.logger.info(f"Agent {agent_id} processing {len(tasks)} tasks")

            for task in tasks:
                try:
                    await task.mark_started()
                    result = await agent.execute_task(task)
                    await task.mark_completed(result)
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"Task execution failed on agent {agent_id}: {str(e)}")
                    error_result = TaskResult(
                        success=False,
                        output=None,
                        error=str(e),
                        execution_time=0.0
                    )
                    await task.mark_completed(error_result)
                    results.append(error_result)

            return results

        async with asyncio.TaskGroup() as group:
            futures = [
                group.create_task(process_agent_tasks(agent.id, agent.tasks))
                for agent in agents
            ]

        for future in futures:
            all_results.extend(future.result())

        return all_results

    def _setup_logger(self) -> logging.Logger:
        """Setup logging"""
        logger = logging.getLogger(f"PilottAI_{self.config.name}")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if self.config.verbose else logging.INFO)
        return logger

    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get result of a specific task"""
        return self._completed_tasks.get(task_id)

    def get_metrics(self) -> Dict[str, Any]:
        """Get system metrics"""
        return {
            "active_agents": len(self.agents),
            "total_tasks": len(self.tasks),
            "completed_tasks": len(self._completed_tasks),
            "running_tasks": len(self._running_tasks),
            "queue_size": self._task_queue.qsize(),
            "is_running": self._started
        }
