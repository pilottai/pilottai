# File: pilott/orchestration/scaling.py

from typing import Dict, List, Optional, Set
import asyncio
from datetime import datetime, timedelta
import traceback
import logging
from pydantic import BaseModel, Field

from pilott.core.agent import BaseAgent, AgentStatus


class FaultToleranceConfig(BaseModel):
    """Configuration for fault tolerance system"""
    health_check_interval: int = Field(
        default=30,
        description="Interval between health checks (seconds)"
    )
    max_recovery_attempts: int = Field(
        default=3,
        description="Maximum number of recovery attempts before replacement"
    )
    recovery_cooldown: int = Field(
        default=300,
        description="Cooldown period between recovery attempts (seconds)"
    )
    heartbeat_timeout: int = Field(
        default=60,
        description="Maximum time between heartbeats (seconds)"
    )
    resource_threshold: float = Field(
        default=0.9,
        description="Maximum resource usage threshold"
    )
    task_timeout: int = Field(
        default=1800,  # 30 minutes
        description="Time before a task is considered stuck"
    )


class FaultTolerance:
    """Manages agent health monitoring and recovery"""

    def __init__(self, orchestrator, config: Optional[Dict] = None):
        self.orchestrator = orchestrator
        self.config = FaultToleranceConfig(**(config or {}))
        self.health_checks: Dict[str, datetime] = {}
        self.recovery_attempts: Dict[str, int] = {}
        self.running = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.logger = logging.getLogger("FaultTolerance")
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging for fault tolerance"""
        self.logger.setLevel(logging.DEBUG if self.orchestrator.verbose else logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(handler)

    async def start(self):
        """Start health monitoring"""
        if self.running:
            self.logger.warning("Fault tolerance monitoring is already running")
            return

        self.running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Fault tolerance monitoring started")

    async def stop(self):
        """Stop health monitoring"""
        if not self.running:
            return

        self.running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Fault tolerance monitoring stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                await self._check_system_health()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {str(e)}\n{traceback.format_exc()}")
                await asyncio.sleep(self.config.health_check_interval)

    async def _check_system_health(self):
        """Check health of all agents"""
        agents = list(self.orchestrator.child_agents.items())
        for agent_id, agent in agents:
            try:
                is_healthy = await self._check_agent_health(agent)
                if not is_healthy:
                    await self._handle_unhealthy_agent(agent)
            except Exception as e:
                self.logger.error(f"Health check failed for agent {agent_id}: {str(e)}")

    async def _check_agent_health(self, agent: BaseAgent) -> bool:
        """Check if an agent is healthy"""
        try:
            # Check multiple health indicators
            checks = await asyncio.gather(
                self._check_heartbeat(agent),
                self._check_resource_usage(agent),
                self._check_task_progress(agent),
                return_exceptions=True
            )

            # Filter out exceptions and check results
            valid_checks = [check for check in checks if not isinstance(check, Exception)]
            if not valid_checks:
                self.logger.error(f"All health checks failed for agent {agent.id}")
                return False

            return all(valid_checks)

        except Exception as e:
            self.logger.error(f"Health check error for {agent.id}: {str(e)}\n{traceback.format_exc()}")
            return False

    async def _check_heartbeat(self, agent: BaseAgent) -> bool:
        """Verify agent is responding"""
        try:
            last_heartbeat = await agent.send_heartbeat()
            timeout = timedelta(seconds=self.config.heartbeat_timeout)
            is_alive = datetime.now() - last_heartbeat < timeout

            if not is_alive:
                self.logger.warning(f"Agent {agent.id} missed heartbeat")

            return is_alive

        except Exception as e:
            self.logger.error(f"Heartbeat check failed for {agent.id}: {str(e)}")
            return False

    async def _check_resource_usage(self, agent: BaseAgent) -> bool:
        """Check if agent's resource usage is within limits"""
        try:
            metrics = await agent.get_metrics()
            usage = metrics.get('resource_usage', 0)
            is_within_limits = usage < self.config.resource_threshold

            if not is_within_limits:
                self.logger.warning(f"Agent {agent.id} resource usage too high: {usage:.2f}")

            return is_within_limits

        except Exception as e:
            self.logger.error(f"Resource check failed for {agent.id}: {str(e)}")
            return False

    async def _check_task_progress(self, agent: BaseAgent) -> bool:
        """Check if agent is making progress on tasks"""
        try:
            stuck_tasks = [task for task in agent.tasks.values()
                           if self._is_task_stuck(task)]

            progress_ok = len(stuck_tasks) == 0
            if not progress_ok:
                self.logger.warning(f"Agent {agent.id} has {len(stuck_tasks)} stuck tasks")

            return progress_ok

        except Exception as e:
            self.logger.error(f"Task progress check failed for {agent.id}: {str(e)}")
            return False

    def _is_task_stuck(self, task: Dict) -> bool:
        """Determine if a task is stuck"""
        if task.get('status') not in ['completed', 'failed']:
            task_age = datetime.now() - datetime.fromisoformat(task['created_at'])
            return task_age.total_seconds() > self.config.task_timeout
        return False

    async def _handle_unhealthy_agent(self, agent: BaseAgent):
        """Handle an unhealthy agent"""
        try:
            if await self._should_attempt_recovery(agent):
                await self._recover_agent(agent)
            else:
                await self._replace_agent(agent)
        except Exception as e:
            self.logger.error(
                f"Failed to handle unhealthy agent {agent.id}: {str(e)}\n{traceback.format_exc()}"
            )

    async def _should_attempt_recovery(self, agent: BaseAgent) -> bool:
        """Determine if recovery should be attempted"""
        agent_id = agent.id

        # Initialize recovery attempts if not present
        if agent_id not in self.recovery_attempts:
            self.recovery_attempts[agent_id] = 0
            return True

        # Check if under max attempts and cooldown period elapsed
        if self.recovery_attempts[agent_id] < self.config.max_recovery_attempts:
            last_attempt = self.health_checks.get(agent_id, datetime.min)
            cooldown = timedelta(seconds=self.config.recovery_cooldown)
            if datetime.now() - last_attempt > cooldown:
                return True

        return False

    async def _recover_agent(self, agent: BaseAgent):
        """Attempt to recover an agent"""
        agent_id = agent.id
        self.recovery_attempts[agent_id] += 1
        self.health_checks[agent_id] = datetime.now()

        try:
            self.logger.info(f"Attempting recovery of agent {agent_id}")

            # Stop agent
            await agent.stop()

            # Reset agent state
            await agent.reset()

            # Restart agent
            await agent.start()

            # Verify recovery
            if await self._check_agent_health(agent):
                self.recovery_attempts[agent_id] = 0
                await self.orchestrator.broadcast_update("agent_recovered", {
                    "agent_id": agent_id,
                    "timestamp": datetime.now().isoformat()
                })
                self.logger.info(f"Successfully recovered agent {agent_id}")
            else:
                raise Exception("Recovery verification failed")

        except Exception as e:
            self.logger.error(f"Recovery failed for {agent_id}: {str(e)}")
            if self.recovery_attempts[agent_id] >= self.config.max_recovery_attempts:
                await self._replace_agent(agent)

    async def _replace_agent(self, agent: BaseAgent):
        """Replace a failed agent"""
        try:
            self.logger.info(f"Replacing failed agent {agent.id}")

            # Create new agent
            new_agent = await self.orchestrator.create_agent(
                role=agent.config.role,
                agent_type=agent.config.role_type
            )

            # Move recoverable tasks
            recoverable_tasks = self._get_recoverable_tasks(agent)
            for task in recoverable_tasks:
                await new_agent.add_task(task)

            # Remove old agent
            await self.orchestrator.remove_child_agent(agent.id)

            # Add new agent
            await self.orchestrator.add_child_agent(new_agent)

            await self.orchestrator.broadcast_update("agent_replaced", {
                "old_agent_id": agent.id,
                "new_agent_id": new_agent.id,
                "timestamp": datetime.now().isoformat(),
                "recovered_tasks": len(recoverable_tasks)
            })

            self.logger.info(
                f"Successfully replaced agent {agent.id} with {new_agent.id}"
            )

        except Exception as e:
            self.logger.error(f"Agent replacement failed: {str(e)}\n{traceback.format_exc()}")

    def _get_recoverable_tasks(self, agent: BaseAgent) -> List[Dict]:
        """Get tasks that can be recovered"""
        return [
            task for task in agent.tasks.values()
            if task['status'] in ['queued', 'in_progress']
               and not task.get('non_recoverable', False)
        ]