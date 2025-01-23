import pytest
from unittest.mock import AsyncMock
from pilott.core import BaseAgent, AgentRole, AgentConfig
from pilott import Serve


@pytest.fixture
def basic_config():
    return AgentConfig(
        role="test_agent",
        role_type=AgentRole.WORKER,
        goal="Test agent functionality",
        description="Agent for testing purposes"
    )


@pytest.fixture
def mock_agent(basic_config):
    from pilott.core.factory import AgentFactory

    class TestAgent(BaseAgent):
        async def evaluate_task_suitability(self, task):
            return 0.8

        async def _default_task_handler(self, task):
            return {"status": "completed", "result": "test_result"}

    AgentFactory.register_agent_type("test_agent", TestAgent)
    return TestAgent


@pytest.fixture
async def setup_pilott():
    pilott = Serve(name="test_pilott")
    await pilott.start()
    return pilott


@pytest.fixture
def mock_orchestrator():
    mock = AsyncMock()
    mock.child_agents = AsyncMock()
    mock.config = AsyncMock()
    mock.config.max_agents = 10
    mock.config.min_agents = 2
    return mock