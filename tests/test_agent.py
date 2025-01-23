import pytest
import asyncio
from pilott.core import AgentStatus, AgentRole


@pytest.mark.asyncio
async def test_agent_initialization(mock_agent, basic_config):
    """Test basic agent initialization"""
    agent = mock_agent(basic_config)
    assert agent.status == AgentStatus.IDLE
    assert agent.role == AgentRole.WORKER
    assert len(agent.child_agents) == 0


@pytest.mark.asyncio
async def test_agent_lifecycle(mock_agent, basic_config):
    """Test agent start and stop"""
    agent = mock_agent(basic_config)
    await agent.start()
    assert agent.status == AgentStatus.IDLE
    await agent.stop()
    assert agent.status == AgentStatus.STOPPED


@pytest.mark.asyncio
async def test_agent_task_execution(mock_agent, basic_config):
    """Test task execution flow"""
    agent = mock_agent(basic_config)
    await agent.start()

    task = {"type": "test_task", "data": "test_data"}
    task_id = await agent.add_task(task)

    await asyncio.sleep(0.1)
    assert agent.tasks[task_id]['status'] == 'completed'
    await agent.stop()