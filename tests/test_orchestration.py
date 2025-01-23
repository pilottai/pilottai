import pytest
from unittest.mock import patch
from unittest.mock import AsyncMock
from pilott.orchestration import DynamicScaling, LoadBalancer, FaultTolerance


@pytest.mark.asyncio
async def test_load_balancer(mock_orchestrator):
    """Test load balancer operations"""
    lb = LoadBalancer(mock_orchestrator)
    await lb.start()
    await lb._balance_system_load()
    await lb.stop()
    assert not lb.running


@pytest.mark.asyncio
async def test_dynamic_scaling(mock_orchestrator):
    scaling = DynamicScaling(mock_orchestrator)
    await scaling.start()

    mock_orchestrator.child_agents = {}
    mock_orchestrator.create_agent = AsyncMock()
    mock_orchestrator.create_agent.return_value = AsyncMock()

    with patch.object(scaling, '_can_scale', return_value=True), \
            patch.object(scaling, '_get_system_load', return_value=0.9):
        await scaling._check_and_adjust_scale()
        assert mock_orchestrator.create_agent.called

    await scaling.stop()


@pytest.mark.asyncio
async def test_fault_tolerance(mock_orchestrator):
    """Test fault tolerance mechanisms"""
    ft = FaultTolerance(mock_orchestrator)
    await ft.start()

    mock_agent = mock_orchestrator
    mock_agent.id = "test_agent"

    with patch.object(ft, '_check_agent_health', return_value=False):
        await ft._handle_unhealthy_agent(mock_agent)
        assert mock_agent.reset.called

    await ft.stop()