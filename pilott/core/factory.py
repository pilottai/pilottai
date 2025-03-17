import asyncio
import logging
import threading
from contextlib import contextmanager
from typing import Dict, Type, Optional, List

from pilott.core.base_agent import BaseAgent
from pilott.core.config import AgentConfig
from pilott.enums.role_e import AgentRole


class AgentFactory:
    """Factory for creating different types of agents"""

    _agent_types: Dict[str, Type[BaseAgent]] = {}
    _active_agents: Dict[str, BaseAgent] = {}
    _logger = logging.getLogger("AgentFactory")
    _register_lock = threading.Lock()
    _creation_lock = asyncio.Lock()

    @classmethod
    def register_agent_type(cls, name: str, agent_class: Type[BaseAgent]):
        """Register a new agent type with validation"""
        if not name or not isinstance(name, str):
            raise ValueError("Agent type name must be a non-empty string")
        if not isinstance(agent_class, type) or not issubclass(agent_class, BaseAgent):
            raise TypeError("agent_class must be a subclass of BaseAgent")

        with cls._register_lock:
            if name in cls._agent_types:
                raise ValueError(f"Agent type {name} already registered")
            cls._agent_types[name] = agent_class
            cls._logger.info(f"Registered new agent type: {name}")


    @classmethod
    @contextmanager
    async def create_managed_agent(cls,
                                   agent_type: str,
                                   config: Optional[AgentConfig] = None,
                                   **kwargs) -> BaseAgent:
        """Create an agent with automatic cleanup on failure"""
        agent = None
        try:
            async with cls._creation_lock:
                agent = await cls.create_agent(agent_type, config, **kwargs)
                yield agent
        except Exception as e:
            if agent and agent.id in cls._active_agents:
                await cls.cleanup_agent(agent.id)
            raise
        finally:
            if agent and agent.id in cls._active_agents:
                await cls.cleanup_agent(agent.id)

    @classmethod
    async def create_agent(cls,
                           agent_type: str,
                           config: Optional[AgentConfig] = None,
                           **kwargs) -> BaseAgent:
        """Create an agent with enhanced error handling and validation"""
        if not agent_type:
            raise ValueError("Agent type cannot be empty")

        async with cls._creation_lock:
            try:
                if agent_type not in cls._agent_types:
                    valid_types = ", ".join(cls._agent_types.keys())
                    raise ValueError(f"Unknown agent type: {agent_type}. Valid types: {valid_types}")

                # Create default config if none provided
                if not config:
                    config = AgentConfig(
                        role=agent_type,
                        role_type=AgentRole.WORKER,
                        goal=f"Execute tasks as a {agent_type}",
                        description=f"Worker agent of type {agent_type}",
                        **kwargs
                    )

                # Validate config
                cls._validate_config(config)

                # Create agent with timeout
                async with asyncio.timeout(30):  # 30 second timeout for agent creation
                    agent = cls._agent_types[agent_type](config)

                    # Initialize agent
                    await agent.start()

                    # Store in active agents
                    cls._active_agents[agent.id] = agent

                    cls._logger.info(f"Created agent of type {agent_type} with ID {agent.id}")
                    return agent

            except asyncio.TimeoutError:
                cls._logger.error(f"Timeout creating agent of type {agent_type}")
                raise
            except Exception as e:
                cls._logger.error(f"Failed to create agent of type {agent_type}: {str(e)}")
                raise


    @classmethod
    async def cleanup_agent(cls, agent_id: str):
        """Clean up an agent's resources"""
        if agent_id in cls._active_agents:
            try:
                agent = cls._active_agents[agent_id]
                await agent.stop()
                await agent.cleanup_resources()
                del cls._active_agents[agent_id]
                cls._logger.info(f"Cleaned up agent {agent_id}")
            except Exception as e:
                cls._logger.error(f"Error cleaning up agent {agent_id}: {str(e)}")
                raise

    @classmethod
    def list_available_types(cls) -> List[str]:
        """List all registered agent types"""
        return list(cls._agent_types.keys())

    @classmethod
    def get_active_agents(cls) -> Dict[str, BaseAgent]:
        """Get all active agents"""
        return cls._active_agents.copy()

    @classmethod
    async def cleanup_all_agents(cls):
        """Clean up all active agents"""
        agent_ids = list(cls._active_agents.keys())
        for agent_id in agent_ids:
            await cls.cleanup_agent(agent_id)

    @classmethod
    def _validate_config(cls, config: AgentConfig):
        """Validate agent configuration"""
        if not config.role:
            raise ValueError("Agent role must be specified")
        if not config.goal:
            raise ValueError("Agent goal must be specified")
        if config.max_iterations < 1:
            raise ValueError("max_iterations must be greater than 0")
        if config.max_task_complexity < 1:
            raise ValueError("max_task_complexity must be greater than 0")
        if config.max_queue_size < 1:
            raise ValueError("max_queue_size must be greater than 0")
        if config.task_timeout < 1:
            raise ValueError("task_timeout must be greater than 0")
