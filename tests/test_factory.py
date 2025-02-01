import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from pilott.core.factory import AgentFactory
from pilott.core.agent import BaseAgent
from pilott.core.config import AgentConfig
from pilott.core.role import AgentRole

class MockAgent(BaseAgent):
    """Proper mock agent that inherits from BaseAgent"""
    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(
                role="test_role",
                role_type=AgentRole.WORKER,
                goal="test goal",
                description="test description"
            )
        self.config = config
        self.id = "test_id"
        self.status = "idle"
        self.start = AsyncMock()
        self.stop = AsyncMock()
        self.cleanup_resources = AsyncMock()



@pytest.mark.asyncio
async def test_register_agent_type():
    # Clear existing registrations
    AgentFactory._agent_types.clear()

    # Test valid registration with proper BaseAgent subclass
    AgentFactory.register_agent_type("test_agent", MockAgent)
    assert "test_agent" in AgentFactory._agent_types

    # Test invalid name
    with pytest.raises(ValueError):
        AgentFactory.register_agent_type("", MockAgent)

    # Test invalid agent class
    with pytest.raises(TypeError):
        AgentFactory.register_agent_type("invalid", object)

    # Test duplicate registration
    with pytest.raises(ValueError):
        AgentFactory.register_agent_type("test_agent", MockAgent)


@pytest.mark.asyncio
async def test_create_managed_agent():
    AgentFactory._agent_types.clear()
    AgentFactory.register_agent_type("test_agent", MockAgent)

    config = AgentConfig(
        role="test_role",
        role_type=AgentRole.WORKER,
        goal="test goal",
        description="test description"
    )

    # Create a manual context manager since we can't use the built-in one
    try:
        agent = await AgentFactory.create_agent("test_agent", config)
        assert isinstance(agent, MockAgent)
        assert agent.id in AgentFactory._active_agents
        yield agent
    finally:
        if agent and agent.id in AgentFactory._active_agents:
            await AgentFactory.cleanup_agent(agent.id)

    # Verify cleanup
    assert agent.id not in AgentFactory._active_agents

    # Test invalid agent type
    try:
        agent = await AgentFactory.create_agent("invalid_type", config)
        yield agent
    except ValueError:
        pass
    finally:
        if agent and agent.id in AgentFactory._active_agents:
            await AgentFactory.cleanup_agent(agent.id)

@pytest.mark.asyncio
async def test_create_agent():
    AgentFactory._agent_types.clear()
    AgentFactory.register_agent_type("test_agent", MockAgent)

    # Test successful creation
    agent = await AgentFactory.create_agent("test_agent")
    assert isinstance(agent, MockAgent)
    assert agent.id in AgentFactory._active_agents

    # Test creation with config
    config = AgentConfig(
        role="test_role",
        role_type=AgentRole.WORKER,
        goal="test goal",
        description="test description"
    )
    agent = await AgentFactory.create_agent("test_agent", config)
    assert isinstance(agent, MockAgent)

    # Test empty agent type
    with pytest.raises(ValueError):
        await AgentFactory.create_agent("")

    # Test unknown agent type
    with pytest.raises(ValueError):
        await AgentFactory.create_agent("unknown_type")

    # Test timeout
    class SlowMockAgent(MockAgent):
        def __init__(self, config: AgentConfig = None):
            super().__init__(config)
            self.start = AsyncMock(side_effect=self._slow_start)

        async def _slow_start(self):
            await asyncio.sleep(2)
            return True

    AgentFactory.register_agent_type("slow_agent", SlowMockAgent)

    # Create a mock timeout context manager
    class MockTimeout:
        def __init__(self, delay):
            self.delay = delay

        async def __aenter__(self):
            raise asyncio.TimeoutError()

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    # Replace the timeout in AgentFactory
    with patch('asyncio.timeout', return_value=MockTimeout(0.1)):
        with pytest.raises(asyncio.TimeoutError):
            await AgentFactory.create_agent("slow_agent")

@pytest.mark.asyncio
async def test_cleanup_agent():
    AgentFactory._agent_types.clear()
    AgentFactory.register_agent_type("test_agent", MockAgent)

    # Create and cleanup agent
    agent = await AgentFactory.create_agent("test_agent")
    await AgentFactory.cleanup_agent(agent.id)
    assert agent.id not in AgentFactory._active_agents

    # Test cleanup of non-existent agent
    await AgentFactory.cleanup_agent("non_existent")  # Should not raise error


@pytest.mark.asyncio
async def test_list_available_types():
    AgentFactory._agent_types.clear()

    # Register test agents
    AgentFactory.register_agent_type("test_agent1", MockAgent)
    AgentFactory.register_agent_type("test_agent2", MockAgent)

    types = AgentFactory.list_available_types()
    assert "test_agent1" in types
    assert "test_agent2" in types
