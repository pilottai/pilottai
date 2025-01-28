from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import uuid
import logging
from enum import Enum

from pydantic import BaseModel, Field, model_validator, ConfigDict, PrivateAttr

from pilott.core.agent import Agent
from pilott.core.config import AgentConfig
from pilott.core.router import TaskRouter
from pilott.orchestration import DynamicScaling, LoadBalancer, FaultTolerance

class ExecutionProcess(str, Enum):
    """Process types for task execution"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    COLLABORATIVE = "collaborative"

class TaskResult(BaseModel):
    """Task execution result"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task: Union[str, Dict]
    result: Any
    agent: str
    status: str = "completed"
    timestamp: datetime = Field(default_factory=datetime.now)
    error: Optional[str] = None

class Serve(BaseModel):
    """
    Main class that orchestrates agents and provides tools to complete assigned jobs.
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        extra='allow'
    )

    # Public fields
    name: str = Field(default="Serve")
    agents: List[Agent] = Field(default_factory=list)
    process: ExecutionProcess = Field(default=ExecutionProcess.SEQUENTIAL)
    verbose: bool = Field(default=False)
    config: Optional[AgentConfig] = None
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), frozen=True)
    task_history: List[TaskResult] = Field(default_factory=list)

    # Private fields using PrivateAttr
    _log: logging.Logger = PrivateAttr()
    _dynamic_scaling: Optional[DynamicScaling] = PrivateAttr(default=None)
    _load_balancer: Optional[LoadBalancer] = PrivateAttr(default=None)
    _fault_tolerance: Optional[FaultTolerance] = PrivateAttr(default=None)
    _task_router: Optional[TaskRouter] = PrivateAttr(default=None)

    @model_validator(mode='after')
    def initialize_systems(self) -> 'Serve':
        """Initialize all systems after model creation"""
        self._setup_logging()
        self._initialize_orchestration()
        return self

    def _setup_logging(self) -> None:
        """Setup logging"""
        self._log = logging.getLogger(f"Serve_{self.id}")
        level = logging.DEBUG if self.verbose else logging.INFO
        self._log.setLevel(level)

        if not self._log.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self._log.addHandler(handler)

    def _initialize_orchestration(self) -> None:
        """Initialize orchestration systems"""
        self._dynamic_scaling = DynamicScaling(self)
        self._load_balancer = LoadBalancer(self)
        self._fault_tolerance = FaultTolerance(self)

        # Create TaskRouter with proper initialization
        self._task_router = TaskRouter(
            name=f"Router_{self.id}",
            verbose=self.verbose,
            serve_ref=self  # Pass serve instance as a reference
        )

    @property
    def child_agents(self) -> Dict[str, Agent]:
        """Get dictionary of agents by ID"""
        return {agent.id: agent for agent in self.agents}

    async def execute(self, tasks: Union[str, List[str], List[Dict]]) -> List[TaskResult]:
        """Execute tasks using appropriate process"""
        # Convert single task to list
        if isinstance(tasks, str):
            tasks = [tasks]

        # Normalize tasks to list of dicts
        normalized_tasks = []
        for task in tasks:
            if isinstance(task, str):
                normalized_tasks.append({
                    "id": str(uuid.uuid4()),
                    "description": task,
                    "type": "default"
                })
            else:
                normalized_tasks.append(task)

        # Execute based on process type
        results = []
        if self.process == ExecutionProcess.SEQUENTIAL:
            results = await self._execute_sequential(normalized_tasks)
        elif self.process == ExecutionProcess.PARALLEL:
            results = await self._execute_parallel(normalized_tasks)
        else:
            results = await self._execute_collaborative(normalized_tasks)

        # Store results in history
        self.task_history.extend(results)
        return results

    async def start(self) -> None:
        """Start the service and all its systems"""
        try:
            # Start orchestration systems
            if self._dynamic_scaling:
                await self._dynamic_scaling.start()
            if self._load_balancer:
                await self._load_balancer.start()
            if self._fault_tolerance:
                await self._fault_tolerance.start()

            # Start all agents
            for agent in self.agents:
                await agent.start()

            self._log.info(f"Serve instance {self.name} started successfully")
        except Exception as e:
            self._log.error(f"Failed to start serve instance: {str(e)}")
            raise

    async def stop(self) -> None:
        """Stop all components"""
        # Stop all agents
        for agent in self.agents:
            await agent.stop()

        # Stop orchestration systems
        if self._dynamic_scaling:
            await self._dynamic_scaling.stop()
        if self._load_balancer:
            await self._load_balancer.stop()
        if self._fault_tolerance:
            await self._fault_tolerance.stop()

        self._log.info(f"Serve instance {self.name} stopped successfully")

    async def _execute_sequential(self, tasks: List[Dict]) -> List[TaskResult]:
        """Execute tasks sequentially"""
        results = []
        last_result = None

        for task in tasks:
            try:
                # Route task using router
                agent_id = self._task_router.route_task(task)
                if not agent_id:
                    raise ValueError("No suitable agent found for task")

                # Find agent
                agent = next((a for a in self.agents if a.id == agent_id), None)
                if not agent:
                    raise ValueError(f"Agent {agent_id} not found")

                # Build context from previous result
                context = last_result.result if last_result else None

                # Execute task
                result = await agent.execute_task(task, str(context) if context else None)

                # Create result
                task_result = TaskResult(
                    task=task,
                    result=result,
                    agent=agent.role,
                    status="completed"
                )

                results.append(task_result)
                last_result = task_result

            except Exception as e:
                self._log.error(f"Task execution failed: {str(e)}")
                error_result = TaskResult(
                    task=task,
                    result=None,
                    agent="unknown",
                    status="failed",
                    error=str(e)
                )
                results.append(error_result)

        return results