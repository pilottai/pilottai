import sys
import asyncio
from typing import Dict, List, Optional, Any, Union

from pilottai.agent import Agent, ActionAgent, MasterAgent, SuperAgent
from pilottai.config.config import Config
from pilottai.core.base_config import LLMConfig, ServeConfig
from pilottai.memory.memory import Memory
from pilottai.config.model import JobResult
from pilottai.job.job import Job
from pilottai.engine.llm import LLMHandler
from pilottai.enums.job_e import JobAssignmentType
from pilottai.utils.agent_utils import AgentUtils
from pilottai.tools.tool import Tool
from pilottai.enums.process_e import ProcessType
from pilottai.utils.job_utils import JobUtility
from pilottai.utils.logger import Logger


class Pilott:
    """
    Main orchestrator for PilottAI framework.
    Handles agent management, job execution, and system lifecycle.
    """

    def __init__(
            self,
            name: str = "PilottAI",
            serve_config: Optional[ServeConfig] = None,
            llm_config: Optional[Union[Dict, LLMConfig]] = None,
            agents: List[Agent] = None,
            tools: Optional[List[Tool]] = None,
            jobs: Optional[Union[str, Job, List[str], List[Job]]] = None,
            job_assignment_type: Optional[Union[str, JobAssignmentType]] = JobAssignmentType.LLM,
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
        self.jobs = self._verify_jobs(jobs)

        # Job management
        self.job_assignment_type = job_assignment_type
        self._job_queue = asyncio.Queue(maxsize=self.config.serve_config.max_queue_size)
        self._running_jobs: Dict[str, asyncio.Task] = {}
        self._completed_jobs: Dict[str, JobResult] = {}

        # Agent management
        self.master_agent = master_agent
        self.super_agents = super_agents
        self.action_agents = action_agents
        self.agentUtility = AgentUtils() if self.jobs else None

        # State management
        self._started = False
        self._shutting_down = False
        self._execution_lock = asyncio.Lock()

        # Memory management
        self.memory = Memory() if self.config.serve_config.memory_enabled else None

        # Setup logging
        self.logger = self._setup_logger()

    def _verify_jobs(self, jobs):
        jobs_obj = JobUtility.to_job_list(jobs)
        return jobs_obj

    async def serve(self) -> List[JobResult] | None:
        """
        Execute a list of agents.

        Returns:
            List[JobResult]: Results of job execution
        """
        if not self._started:
            await self.start()

        try:
            agent_execution = []
            if self.agentUtility is None:
                self.agentUtility = AgentUtils()

            if self.jobs:
                for job in self.jobs:
                    agent_by_job = self._get_agent_by_job(job, self.agents)
                    agent_execution.append(agent_by_job)
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
            self.logger.error(f"Job execution failed: {str(e)}")
            raise

    async def add_agent(self, title: str, goal: str, description: str, tools: Optional[List[Tool]] = None, llm_config: Optional[LLMConfig] = None):
        if self.agents is None:
            self.agents = []
        agent = Agent(title=title, goal=goal, description=description, tools=tools, llm_config=llm_config)
        self.agents.append(agent)
        return agent

    async def add_jobs(self, jobs: Union[str, Job, List[str], List[Job]]):
        if self.jobs is None:
            self.jobs = []
        self.jobs.extend(JobUtility.to_job_list(jobs))


    async def _get_agent_by_job(self, job: Job, agents: List[Agent]):
        """Assign agent to each independent job"""
        agent, score = self.agentUtility.assign_job(job, agents, llm_handler=self.llm, assignment_strategy=self.job_assignment_type)
        agent.jobs.append(job)
        return agent

    async def _execute_parallel(self, agents: List[Agent]) -> List[JobResult]:
        """
        Execute all agents with their assigned job in parallel.

        Args:
            agents: List of agents to execute in parallel

        Returns:
            List of job results from all agents
        """
        # Create a list of execution coroutines for each agent
        execution_jobs = []

        for agent in agents:
            if hasattr(agent, 'job') and agent.jobs:
                execution_jobs.append(self._process_agent_jobs(agent))

        if not execution_jobs:
            return []

        # Execute all agents in parallel
        results = await asyncio.gather(*execution_jobs, return_exceptions=True)

        # Flatten and process the results
        all_results = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Agent execution failed: {str(result)}")
                # We don't know which agent failed, so we can't create specific JobResults
                continue
            elif isinstance(result, list):
                all_results.extend(result)
            else:
                all_results.append(result)

        return all_results

    async def _execute_sequential(self, agents: List[Agent]) -> List[JobResult]:
        """
        Execute all agents with their assigned job sequentially.

        Args:
            agents: List of agents to execute sequentially

        Returns:
            List of job results from all agents
        """
        all_results = []

        # Process each agent in sequence
        for agent in agents:
            try:
                results = await self._process_agent_jobs(agent)
                if isinstance(results, list):
                    all_results.extend(results)
            except Exception as e:
                self.logger.error(f"Agent {agent.id} execution failed: {str(e)}")
                # Create a failure result for each job
                for job in agent.jobs:
                    job_id = job.id if hasattr(job, 'id') else "unknown"
                    all_results.append(JobResult(
                        success=False,
                        output=None,
                        error=f"Agent {agent.id} execution error: {str(e)}",
                        execution_time=0.0,
                        metadata={"agent_id": agent.id, "job_id": job_id}
                    ))

        return all_results

    async def _process_agent_jobs(self, agent: Agent) -> List[JobResult]:
        """
        Helper method to process all job for a given agent.

        Args:
            agent: The agent whose job will be processed

        Returns:
            List of job results
        """
        results = []

        for job in agent.jobs:
            try:
                # Start job execution
                await job.mark_started(agent_id=agent.id)

                # Execute the job through the agent
                result = await agent.execute_job(job, dependent_agent=agent.depends_on, args=agent.args)

                # Complete the job with the result
                await job.mark_completed(result)
                agent.output = result
                results.append(result)
            except Exception as e:
                self.logger.error(f"Job {job.id if hasattr(job, 'id') else 'unknown'} execution failed: {str(e)}")

                # Create a failure result
                error_result = JobResult(
                    success=False,
                    output=None,
                    error=str(e),
                    execution_time=0.0,
                    metadata={"agent_id": agent.id}
                )

                # Mark the job as completed with error
                try:
                    await job.mark_completed(error_result)
                except Exception:
                    pass  # Ignore errors in marking completion

                results.append(error_result)

        return results

    async def _execute_hierarchical(self, jobs: List[Job]) -> List[JobResult]:
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

    async def delegate(self, agents: List[Agent], parallel: bool = False) -> List[JobResult]:
        if not self._started:
            await self.start()

        try:
            if parallel:
                return await self._execute_agents_parallel(agents)
            return await self._execute_agents_sequential(agents)

        except Exception as e:
            self.logger.error(f"Agent-based execution failed: {str(e)}")
            raise

    async def _execute_agents_sequential(self, agents: List[Agent]) -> List[JobResult]:
        """Execute job through agents sequentially."""
        all_results = []

        for agent in agents:

            for job in agent.jobs:
                try:
                    await job.mark_started()
                    result = await agent.execute_job(job, agent.depends_on, args=agent.args)
                    await job.mark_completed(result)
                    all_results.append(result)
                except Exception as e:
                    self.logger.error(f"Job execution failed on agent {agent.id}: {str(e)}")
                    error_result = JobResult(
                        success=False,
                        output=None,
                        error=str(e),
                        execution_time=0.0
                    )
                    await job.mark_completed(error_result)
                    all_results.append(error_result)

        return all_results

    async def _execute_agents_parallel(self, agents: List[Agent]) -> List[JobResult]:
        """Execute job through agents in parallel."""
        all_results = []

        async def process_agent_jobs(agent_id, jobs):
            agent = self.agents[agent_id]
            results = []
            self.logger.info(f"Agent {agent_id} processing {len(jobs)} job")

            for job in jobs:
                try:
                    await job.mark_started()
                    result = await agent.execute_job(job, agent.depends_on, args=agent.args)
                    await job.mark_completed(result)
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"Job execution failed on agent {agent_id}: {str(e)}")
                    error_result = JobResult(
                        success=False,
                        output=None,
                        error=str(e),
                        execution_time=0.0
                    )
                    await job.mark_completed(error_result)
                    results.append(error_result)

            return results


        jobs = [
            process_agent_jobs(agent.id, agent.jobs)
            for agent in agents
        ]
        results = await asyncio.gather(*jobs, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                all_results.extend(result)
            else:
                all_results.append(result)

        return all_results

    def _setup_logger(self) -> Logger:
        """Setup logging"""
        logger = Logger(f"PilottAI_{self.config.name}")
        if not logger.handlers:
            handler = logger.StreamHandler()
            formatter = logger.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(logger.DEBUG if self.config.serve_config.verbose else logger.INFO)
        return logger

    async def get_job_result(self, job_id: str) -> Optional[JobResult]:
        """Get result of a specific job"""
        return self._completed_jobs.get(job_id)

    def get_metrics(self) -> Dict[str, Any]:
        """Get system metrics"""
        return {
            "active_agents": len(self.agents),
            "total_jobs": len(self.jobs),
            "is_running": self._started
        }
