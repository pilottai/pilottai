from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import uuid
import asyncio

from pydantic import (
    UUID4,
    BaseModel,
    Field,
    field_validator,
    ConfigDict
)

from pydantic_core import PydanticCustomError

from pilott.core import BaseAgent, AgentRole
from pilott.core import AgentConfig
from pilott.core import Memory
from pilott.core import AgentFactory
from pilott.core import TaskRouter
from pilott.tools import Tool
from pilott.orchestration import DynamicScaling
from pilott.orchestration import LoadBalancer
from pilott.orchestration import FaultTolerance
from pilott.utils import setup_logger

class Serve(BaseModel):
    """
    Main class that orchestrates agents and provides tools to complete assigned jobs.
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra='allow'
    )

    name: str = Field(default="", description="Name of the bot.")
    agents: List[BaseAgent] = Field(default_factory=list, description="List of agents part of this pilott.")
    tools: List[Tool] = Field(default_factory=list, description="Tools at agents disposal")
    verbose: Union[int, bool] = Field(
        default=0,
        description="Indicates the verbosity level for logging during execution."
    )
    memory: Optional[Memory] = Field(
        default_factory=Memory,
        description="Memory management for the pilott"
    )
    id: UUID4 = Field(
        default_factory=uuid.uuid4,
        frozen=True,
        description="A unique identifier for the pilott instance."
    )
    config: AgentConfig = Field(
        default_factory=lambda: AgentConfig(
            role="orchestrator",
            role_type=AgentRole.ORCHESTRATOR,
            goal="Orchestrate and manage agent operations",
            description="Main orchestrator for the pilott system"
        )
    )
    child_agents: Dict[str, BaseAgent] = Field(default_factory=dict)
    # Systems
    dynamic_scaling: Optional[DynamicScaling] = None
    load_balancer: Optional[LoadBalancer] = None
    fault_tolerance: Optional[FaultTolerance] = None
    task_router: Optional[TaskRouter] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.logger = setup_logger(self)
        self._initialize_systems()

    def _initialize_systems(self):
        """Initialize orchestration systems"""
        self.dynamic_scaling = DynamicScaling(self)
        self.load_balancer = LoadBalancer(self)
        self.fault_tolerance = FaultTolerance(self)
        self.task_router = TaskRouter(pilott=self)

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
        # Start orchestration systems
        await asyncio.gather(
            self.dynamic_scaling.start(),
            self.load_balancer.start(),
            self.fault_tolerance.start()
        )

        # Initialize and start agents
        for agent in self.agents:
            await agent.start()

        self.logger.info(f"Pilott {self.name} started successfully")

    async def add_agent(self,
                        agent_type: str,
                        config: Optional[AgentConfig] = None,
                        **kwargs) -> BaseAgent:
        """Add a new agent to the pilott using the factory"""
        agent = AgentFactory.create_agent(agent_type, config, **kwargs)
        self.agents.append(agent)
        await agent.start()
        self.logger.info(f"Added new agent: {agent.id} of type {agent_type}")
        return agent

    async def remove_agent(self, agent_id: str):
        """Remove an agent from the pilott"""
        agent = next((a for a in self.agents if a.id == agent_id), None)
        if agent:
            self.agents.remove(agent)
            await agent.stop()
            self.logger.info(f"Removed agent: {agent_id}")

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
        # Get task priority
        priority = self.task_router.get_task_priority(task)
        task['priority'] = priority

        # Find suitable agent
        agent_id = self.task_router.route_task(task)
        if not agent_id:
            raise ValueError("No suitable agent found for task")

        agent = next(a for a in self.agents if a.id == agent_id)
        return await agent.execute_task(task)

    async def stop(self):
        """Stop the pilott and all its components"""
        # Stop all agents
        for agent in self.agents:
            await agent.stop()

        # Stop orchestration systems
        if self.dynamic_scaling:
            await self.dynamic_scaling.stop()
        if self.load_balancer:
            await self.load_balancer.stop()
        if self.fault_tolerance:
            await self.fault_tolerance.stop()

        self.logger.info(f"Pilott {self.name} stopped successfully")