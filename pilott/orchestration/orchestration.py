from typing import Dict, Optional
from datetime import datetime, timedelta
import asyncio
import psutil
import logging
from pydantic import BaseModel, Field


class ScalingConfig(BaseModel):
    """Configuration for dynamic scaling"""
    scale_up_threshold: float = Field(
        default=0.8,
        description="Load threshold to trigger scaling up (0-1)"
    )
    scale_down_threshold: float = Field(
        default=0.3,
        description="Load threshold to trigger scaling down (0-1)"
    )
    min_agents: int = Field(
        default=2,
        description="Minimum number of agents to maintain"
    )
    max_agents: int = Field(
        default=10,
        description="Maximum number of agents allowed"
    )
    cooldown_period: int = Field(
        default=300,
        description="Cooldown period in seconds between scaling operations"
    )
    check_interval: int = Field(
        default=60,
        description="Interval in seconds between load checks"
    )
    scale_up_increment: int = Field(
        default=1,
        description="Number of agents to add when scaling up"
    )
    scale_down_increment: int = Field(
        default=1,
        description="Number of agents to remove when scaling down"
    )


class DynamicScaling:
    """Manages dynamic scaling of agents based on system load"""

    def __init__(self, orchestrator, config: Optional[Dict] = None):
        self.orchestrator = orchestrator
        self.config = ScalingConfig(**(config or {}))
        self.logger = logging.getLogger("DynamicScaling")
        self.running = False
        self.scaling_task: Optional[asyncio.Task] = None
        self.metrics_history = []  # Initialize metrics history
        self.last_scale_time = datetime.now()
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging for dynamic scaling"""
        level = logging.DEBUG if self.orchestrator.verbose else logging.INFO
        self.logger.setLevel(level)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(handler)

    async def start(self):
        """Start the dynamic scaling monitor"""
        if self.running:
            self.logger.warning("Dynamic scaling is already running")
            return

        self.running = True
        self.scaling_task = asyncio.create_task(self._scaling_loop())
        self.logger.info("Dynamic scaling started")

    async def stop(self):
        """Stop the dynamic scaling monitor"""
        if not self.running:
            return

        self.running = False
        if self.scaling_task:
            self.scaling_task.cancel()
            try:
                await self.scaling_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Dynamic scaling stopped")

    async def _scaling_loop(self):
        """Main loop for monitoring and scaling"""
        while self.running:
            try:
                await self._check_and_adjust_scale()
                await asyncio.sleep(self.config.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in scaling loop: {str(e)}")
                await asyncio.sleep(self.config.check_interval)

    async def _check_and_adjust_scale(self):
        """Check system load and adjust agent count if necessary"""
        try:
            current_load = await self._get_system_load()
            self._update_metrics_history(current_load)

            if not self._can_scale():
                return

            if current_load > self.config.scale_up_threshold:
                await self._scale_up()
            elif current_load < self.config.scale_down_threshold:
                await self._scale_down()

        except Exception as e:
            self.logger.error(f"Error adjusting scale: {str(e)}")

    async def _get_system_load(self) -> float:
        """Calculate current system load using multiple metrics"""
        try:
            # Get agent metrics
            agent_metrics = [
                await agent.get_metrics()
                for agent in self.orchestrator.child_agents.values()
            ]

            # Calculate various load factors
            num_agents = len(self.orchestrator.child_agents)
            if num_agents == 0:
                return 0.0

            # Task load
            total_tasks = sum(metrics['total_tasks'] for metrics in agent_metrics)
            max_tasks = num_agents * 10  # Assuming 10 tasks per agent is optimal
            task_load = min(1.0, total_tasks / max_tasks)

            # Queue utilization
            avg_queue_util = sum(
                metrics['queue_utilization']
                for metrics in agent_metrics
            ) / num_agents

            # System resources
            cpu_load = psutil.cpu_percent() / 100
            memory_load = psutil.virtual_memory().percent / 100

            # Weighted average of all metrics
            load = (
                    0.35 * task_load +
                    0.25 * avg_queue_util +
                    0.20 * cpu_load +
                    0.20 * memory_load
            )

            self.logger.debug(
                f"Load metrics - Task: {task_load:.2f}, Queue: {avg_queue_util:.2f}, "
                f"CPU: {cpu_load:.2f}, Memory: {memory_load:.2f}, Total: {load:.2f}"
            )

            return min(1.0, load)

        except Exception as e:
            self.logger.error(f"Error calculating system load: {str(e)}")
            return 0.0

    def _update_metrics_history(self, current_load: float):
        """Update metrics history for trend analysis"""
        self.metrics_history.append({
            'timestamp': datetime.now(),
            'load': current_load,
            'num_agents': len(self.orchestrator.child_agents)
        })

        # Keep only last hour of metrics
        cutoff = datetime.now() - timedelta(hours=1)
        self.metrics_history = [
            m for m in self.metrics_history
            if m['timestamp'] > cutoff
        ]

    def _analyze_load_trend(self) -> float:
        """Analyze load trend to make better scaling decisions"""
        if len(self.metrics_history) < 5:
            return 0.0

        recent_loads = [m['load'] for m in self.metrics_history[-5:]]
        return sum(recent_loads) / len(recent_loads)

    async def _scale_up(self):
        """Add new agents to handle increased load"""
        current_agents = len(self.orchestrator.child_agents)
        if current_agents >= self.config.max_agents:
            self.logger.info("Cannot scale up: maximum agents reached")
            return

        try:
            agents_to_add = min(
                self.config.scale_up_increment,
                self.config.max_agents - current_agents
            )

            for _ in range(agents_to_add):
                new_agent = await self.orchestrator.create_agent()
                await self.orchestrator.add_child_agent(new_agent)

            self.last_scale_time = datetime.now()
            self.logger.info(f"Scaled up by {agents_to_add} agents")

        except Exception as e:
            self.logger.error(f"Error scaling up: {str(e)}")

    async def _scale_down(self):
        """Remove underutilized agents"""
        current_agents = len(self.orchestrator.child_agents)
        if current_agents <= self.config.min_agents:
            self.logger.info("Cannot scale down: minimum agents reached")
            return

        try:
            agents_to_remove = min(
                self.config.scale_down_increment,
                current_agents - self.config.min_agents
            )

            removed = 0
            for _ in range(agents_to_remove):
                idle_agent = await self._find_idle_agent()
                if idle_agent:
                    await self.orchestrator.remove_child_agent(idle_agent.id)
                    removed += 1

            if removed > 0:
                self.last_scale_time = datetime.now()
                self.logger.info(f"Scaled down by {removed} agents")

        except Exception as e:
            self.logger.error(f"Error scaling down: {str(e)}")

    def _can_scale(self) -> bool:
        """Check if scaling is allowed based on cooldown and conditions"""
        if not self.running:
            return False

        cooldown_elapsed = (
                                   datetime.now() - self.last_scale_time
                           ).seconds > self.config.cooldown_period

        if not cooldown_elapsed:
            self.logger.debug("Scaling cooldown period not elapsed")
            return False

        return True

    async def _find_idle_agent(self) -> Optional['BaseAgent']:
        """Find an idle agent suitable for removal"""
        try:
            idle_agents = []
            for agent in self.orchestrator.child_agents.values():
                metrics = await agent.get_metrics()
                if (agent.status == 'idle' and
                        metrics['total_tasks'] == 0 and
                        metrics['queue_utilization'] == 0):
                    idle_agents.append((agent, metrics['success_rate']))

            # Sort by success rate ascending (remove less successful agents first)
            idle_agents.sort(key=lambda x: x[1])
            return idle_agents[0][0] if idle_agents else None

        except Exception as e:
            self.logger.error(f"Error finding idle agent: {str(e)}")
            return None

    async def get_scaling_metrics(self) -> Dict:
        """Get current scaling metrics"""
        return {
            'current_agents': len(self.orchestrator.child_agents),
            'load_history': self.metrics_history[-10:] if self.metrics_history else [],
            'last_scale_time': self.last_scale_time.isoformat(),
            'can_scale_up': len(self.orchestrator.child_agents) < self.config.max_agents,
            'can_scale_down': len(self.orchestrator.child_agents) > self.config.min_agents
        }