import sys
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union

from pilottai.agent import Agent, ActionAgent, MasterAgent, SuperAgent
from pilottai.config.config import Config
from pilottai.core.base_config import LLMConfig, ServeConfig
from pilottai.memory.memory import Memory
from pilottai.config.model import TaskResult
from pilottai.task.task import Task
from pilottai.engine.llm import LLMHandler
from pilottai.enums.task_e import TaskAssignmentType
from pilottai.utils.agent_utils import AgentUtils
from pilottai.tools.tool import Tool
from pilottai.enums.process_e import ProcessType
from pilottai.utils.task_utils import TaskUtility


class Pilott:
    """
    Main orchestrator for PilottAI framework.
    Handles agent management, task execution, and system lifecycle.
    """

    def __init__(
            self,
            name: str = "PilottAI",
            serve_config: Optional[ServeConfig] = None,
            llm_config: Optional[Union[Dict, LLMConfig]] = None,
            agents: List[Agent] = None,
            tools: Optional[List[Tool]] = None,
            tasks: Optional[Union[str, Task, List[str], List[Task]]] = None,
            task_assignment_type: Optional[Union[str, TaskAssignmentType]] = TaskAssignmentType.LLM,
            master_agent: Optional[MasterAgent] = None,
            super_agents: List[SuperAgent] = None,
            action_agents: List[ActionAgent] = None,
      ):
        # Initialize configuration
        self.config = Config(name = name, serve_config=serve_config, llm_config=llm_config)

        # Core components
        self.agents = agents
        self.llm = LLMHandler(llm_config)
        self.tools = tools
        self.tasks = self._verify_tasks(tasks)

        # Task management
        self.task_assignment_type = task_assignment_type
        self._task_queue = asyncio.Queue(maxsize=self.config.serve_config.max_queue_size)
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._completed_tasks: Dict[str, TaskResult] = {}

        # Agent management
        self.master_agent = master_agent
        self.super_agents = super_agents
        self.action_agents = action_agents
        self.agentUtility = AgentUtils() if self.tasks else None

        # State management
        self._started = False
        self._shutting_down = False
        self._execution_lock = asyncio.Lock()

        # Memory management
        self.memory = Memory() if self.config.serve_config.memory_enabled else None

        # Setup logging
        self.logger = self._setup_logger()

    def _verify_tasks(self, tasks):
        tasks_obj = None
        if isinstance(tasks, str):
            tasks_obj = TaskUtility.to_task_list(tasks)
        elif isinstance(tasks, list):
            tasks_obj = TaskUtility.to_task_list(tasks)
        return tasks_obj

    async def serve(self) -> List[TaskResult] | None:
        """
        Execute a list of agents.

        Returns:
            List[TaskResult]: Results of task execution
        """
        if not self._started:
            await self.start()

        try:
            agent_execution = []
            if self.agentUtility is None:
                self.agentUtility = AgentUtils()

            if self.tasks:
                for task in self.tasks:
                    agent_by_task = self._get_agent_by_task(task, self.agents)
                    agent_execution.append(agent_by_task)
            if isinstance(self.agents, list):
                agent_execution.extend(self.agents)
            elif isinstance(self.agents, Agent):
                agent_execution.append(self.agents)

            if self.config.serve_config.process_type == ProcessType.SEQUENTIAL:
                return await self._execute_sequential(agent_execution)
            elif self.config.serve_config.process_type == ProcessType.PARALLEL:
                return await self._execute_parallel(agent_execution)
            elif self.config.serve_config.process_type == ProcessType.HIERARCHICAL:
                return await self._execute_hierarchical(agent_execution)
            return await self._execute_sequential(agent_execution)
        except Exception as e:
            self.logger.error(f"Task execution failed: {str(e)}")
            raise

    async def _get_agent_by_task(self, task: Task, agents: List[Agent]):
        """Assign agent to each independent task"""
        agent, score = self.agentUtility.assign_task(task, agents, llm_handler=self.llm, assignment_strategy=self.task_assignment_type)
        agent.tasks.append(task)
        return agent

    async def _execute_parallel(self, agents: List[Agent]) -> List[TaskResult]:
        """
        Execute all agents with their assigned task in parallel.

        Args:
            agents: List of agents to execute in parallel

        Returns:
            List of task results from all agents
        """
        # Create a list of execution coroutines for each agent
        execution_tasks = []

        for agent in agents:
            if hasattr(agent, 'task') and agent.tasks:
                execution_tasks.append(self._process_agent_tasks(agent))

        if not execution_tasks:
            return []

        # Execute all agents in parallel
        results = await asyncio.gather(*execution_tasks, return_exceptions=True)

        # Flatten and process the results
        all_results = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Agent execution failed: {str(result)}")
                # We don't know which agent failed, so we can't create specific TaskResults
                continue
            elif isinstance(result, list):
                all_results.extend(result)
            else:
                all_results.append(result)

        return all_results

    async def _execute_sequential(self, agents: List[Agent]) -> List[TaskResult]:
        """
        Execute all agents with their assigned task sequentially.

        Args:
            agents: List of agents to execute sequentially

        Returns:
            List of task results from all agents
        """
        all_results = []

        # Process each agent in sequence
        for agent in agents:
            try:
                results = await self._process_agent_tasks(agent)
                if isinstance(results, list):
                    all_results.extend(results)
                else:
                    all_results.append(results)
            except Exception as e:
                self.logger.error(f"Agent {agent.id} execution failed: {str(e)}")
                # Create a failure result for each task
                for task in agent.tasks:
                    task_id = task.id if hasattr(task, 'id') else "unknown"
                    all_results.append(TaskResult(
                        success=False,
                        output=None,
                        error=f"Agent {agent.id} execution error: {str(e)}",
                        execution_time=0.0,
                        metadata={"agent_id": agent.id, "task_id": task_id}
                    ))

        return all_results

    async def _process_agent_tasks(self, agent: Agent) -> List[TaskResult]:
        """
        Helper method to process all task for a given agent.

        Args:
            agent: The agent whose task will be processed

        Returns:
            List of task results
        """
        results = []

        for task in agent.tasks:
            try:
                # Start task execution
                await task.mark_started(agent_id=agent.id)

                # Execute the task through the agent
                result = await agent.execute_task(task, dependent_agent=agent.depends_on, args=agent.args)

                # Complete the task with the result
                await task.mark_completed(result)
                agent.output = result
                results.append(result)
            except Exception as e:
                self.logger.error(f"Task {task.id if hasattr(task, 'id') else 'unknown'} execution failed: {str(e)}")

                # Create a failure result
                error_result = TaskResult(
                    success=False,
                    output=None,
                    error=str(e),
                    execution_time=0.0,
                    metadata={"agent_id": agent.id}
                )

                # Mark the task as completed with error
                try:
                    await task.mark_completed(error_result)
                except Exception:
                    pass  # Ignore errors in marking completion

                results.append(error_result)

        return results

    async def _execute_hierarchical(self, tasks: List[Task]) -> List[TaskResult]:
        pass

    async def start(self):
        """Start the Serve orchestrator"""
        if self._started:
            return

        try:
            # Start all agents
            for agent in self.agents:
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

            self._started = False
            self._shutting_down = False
            self.logger.info("PilottAI Serve stopped")

        except Exception as e:
            self.logger.error(f"Failed to stop Serve: {str(e)}")
            raise

    async def delegate(self, agents: List[Agent], parallel: bool = False) -> List[TaskResult]:
        if not self._started:
            await self.start()

        try:
            if parallel:
                return await self._execute_agents_parallel(agents)
            return await self._execute_agents_sequential(agents)

        except Exception as e:
            self.logger.error(f"Agent-based execution failed: {str(e)}")
            raise

    async def _execute_agents_sequential(self, agents: List[Agent]) -> List[TaskResult]:
        """Execute task through agents sequentially."""
        all_results = []

        for agent in agents:

            for task in agent.tasks:
                try:
                    await task.mark_started()
                    result = await agent.execute_task(task, agent.depends_on, args=agent.args)
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

    async def _execute_agents_parallel(self, agents: List[Agent]) -> List[TaskResult]:
        """Execute task through agents in parallel."""
        all_results = []

        async def process_agent_tasks(agent_id, tasks):
            agent = self.agents[agent_id]
            results = []
            self.logger.info(f"Agent {agent_id} processing {len(tasks)} task")

            for task in tasks:
                try:
                    await task.mark_started()
                    result = await agent.execute_task(task, agent.depends_on, args=agent.args)
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

        if sys.version_info >= (3, 11):
            async with asyncio.TaskGroup() as group:
                futures = [
                    group.create_task(process_agent_tasks(agent.id, agent.tasks))
                    for agent in agents
                ]
            for future in futures:
                all_results.extend(future.result())

            # Python < 3.11 — fallback to asyncio.gather
        else:
            tasks = [
                process_agent_tasks(agent.id, agent.tasks)
                for agent in agents
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_results.extend(result)
                else:
                    all_results.append(result)

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
        logger.setLevel(logging.DEBUG if self.config.serve_config.verbose else logging.INFO)
        return logger

    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get result of a specific task"""
        return self._completed_tasks.get(task_id)

    def get_metrics(self) -> Dict[str, Any]:
        """Get system metrics"""
        return {
            "active_agents": len(self.agents),
            "total_tasks": len(self.tasks),
            "is_running": self._started
        }
