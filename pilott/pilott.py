from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import uuid
import asyncio
import logging

from pydantic import (
    UUID4,
    BaseModel,
    Field,
    field_validator,
    ConfigDict,
    PrivateAttr
)

from pydantic_core import PydanticCustomError

from pilott.core import BaseAgent
from pilott.core import AgentConfig
from pilott.core import Memory
from pilott.core import TaskRouter
from pilott.tools import Tool
from pilott.orchestration import DynamicScaling
from pilott.orchestration import LoadBalancer
from pilott.orchestration import FaultTolerance

class Serve(BaseModel):
    """
    Main class that orchestrates agents and provides tools to complete assigned jobs.
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        use_enum_values=True
    )

    name: str = Field(default="")
    verbose: Union[int, bool] = Field(default=0)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    config: Optional[AgentConfig] = None

    _logger: Any = PrivateAttr()
    _dynamic_scaling: Any = PrivateAttr()
    _load_balancer: Any = PrivateAttr()
    _fault_tolerance: Any = PrivateAttr()
    _task_router: Any = PrivateAttr()
    _agents: List[BaseAgent] = PrivateAttr(default=list)
    _child_agents: Dict[str, BaseAgent] = PrivateAttr(default=dict)

    def model_post_init(self, context: Optional[Dict] = None) -> None:
        self._agents = []
        self._child_agents = {}
        self._setup_logging()
        self._initialize_systems()

    def _setup_logging(self):
        """Setup logging for the Serve instance"""
        self._logger = logging.getLogger(f"Serve_{self.id}")
        level = logging.DEBUG if self.verbose else logging.INFO
        self.logger.setLevel(level)

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def _initialize_systems(self):
        """Initialize orchestration systems"""
        self._dynamic_scaling = DynamicScaling(self)
        self._load_balancer = LoadBalancer(self)
        self._fault_tolerance = FaultTolerance(self)
        self._task_router = TaskRouter(pilott=self)

    @property
    def agents(self) -> List[BaseAgent]:
        """Get list of agents"""
        return self._agents

    @property
    def child_agents(self) -> Dict[str, BaseAgent]:
        """Get dictionary of child agents"""
        return self._child_agents

    @property
    def logger(self) -> logging.Logger:
        """Access logger as a property"""
        return self._logger

    @property
    def dynamic_scaling(self) -> Any:
        return self._dynamic_scaling

    @property
    def load_balancer(self) -> Any:
        return self._load_balancer

    @property
    def fault_tolerance(self) -> Any:
        return self._fault_tolerance

    @property
    def task_router(self) -> Any:
        return self._task_router

    @field_validator("id", mode="before")
    @classmethod
    def _deny_user_set_id(cls, v: Optional[UUID4]) -> None:
        """Prevent manual setting of the 'id' field by users."""
        if v:
            raise PydanticCustomError(
                "may_not_set_field", "The 'id' field cannot be set by the user.", {}
            )

    async def start(self):
        """Start the pilott and its systems"""
        try:
            await asyncio.gather(
                self._dynamic_scaling.start(),
                self._load_balancer.start(),
                self._fault_tolerance.start()
            )

            # Initialize and start agents
            for agent in self._agents:
                await agent.start()

            self._logger.info(f"Pilott {self.name} started successfully")
        except Exception as e:
            self._logger.error(f"Failed to start pilott: {str(e)}")
            raise

    async def add_agent(self, agent: BaseAgent):
        """Add a new agent to the pilott"""
        try:
            if not isinstance(agent, BaseAgent):
                raise ValueError("agent must be an instance of BaseAgent")

            self._agents.append(agent)
            self._child_agents[agent.id] = agent
            self._logger.info(f"Added new agent: {agent.id}")
        except Exception as e:
            self.logger.error(f"Failed to add agent: {str(e)}")
            raise

    async def remove_agent(self, agent_id: str):
        """Remove an agent from the pilott"""
        try:
            if agent_id in self._child_agents:
                agent = self._child_agents[agent_id]
                await agent.stop()
                self._agents = [a for a in self._agents if a.id != agent_id]
                del self._child_agents[agent_id]
                self._logger.info(f"Removed agent: {agent_id}")
        except Exception as e:
            self._logger.error(f"Failed to remove agent: {str(e)}")
            raise

    async def get_system_status(self) -> Dict:
        """Get comprehensive system status"""
        return {
            "id": str(self.id),
            "name": self.name,
            "agent_count": len(self.agents),
            "agents": [await agent.get_status() for agent in self.agents],
            "memory_usage": self.memory.get_usage() if self.memory else None,
            "timestamp": datetime.now().isoformat()
        }

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task using the router to find suitable agent"""
        try:
            if not self._agents:
                raise ValueError("No agents available to execute task")
            agent = self._agents[0]
            self._logger.info(f"Executing task using agent {agent.id}")
            task_copy = task.copy()
            return await agent.execute_task(task_copy)
        except Exception as e:
            self._logger.error(f"Task execution failed: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def stop(self):
        """Stop the pilott and all its components"""
        for agent in self._agents:
            await agent.stop()

        if self._dynamic_scaling:
            await self._dynamic_scaling.stop()
        if self._load_balancer:
            await self._load_balancer.stop()
        if self._fault_tolerance:
            await self._fault_tolerance.stop()

        self._logger.info(f"Pilott {self.name} stopped successfully")