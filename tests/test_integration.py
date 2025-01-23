import pytest
from pilott.core.router import TaskPriority


@pytest.mark.asyncio
async def test_pilott_integration(setup_pilott, mock_agent, basic_config):
    pilott = await setup_pilott
    agent = await pilott.add_agent("test_agent", basic_config)
    assert len(pilott.agents) == 1