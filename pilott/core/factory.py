from typing import Dict, Type, Optional
from pilott.core.agent import BaseAgent
from pilott.core.role import AgentRole
from pilott.core.config import AgentConfig


class AgentFactory:
    """Factory for creating different types of agents"""
    
    _agent_types: Dict[str, Type[BaseAgent]] = {}

    @classmethod
    def register_agent_type(cls, name: str, agent_class: Type[BaseAgent]):
        """Register a new agent type"""
        cls._agent_types[name] = agent_class

    @classmethod
    def create_agent(cls, 
                    agent_type: str, 
                    config: Optional[AgentConfig] = None,
                    **kwargs) -> BaseAgent:
        """Create an agent of the specified type"""
        if agent_type not in cls._agent_types:
            raise ValueError(f"Unknown agent type: {agent_type}")
            
        if not config:
            config = AgentConfig(
                role=agent_type,
                role_type=AgentRole.WORKER,
                goal=f"Execute tasks as a {agent_type}",
                description=f"Worker agent of type {agent_type}",
                **kwargs
            )
            
        return cls._agent_types[agent_type](config)

    @classmethod
    def list_available_types(cls) -> list:
        """List all registered agent types"""
        return list(cls._agent_types.keys())