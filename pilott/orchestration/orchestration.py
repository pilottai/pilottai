import asyncio
import logging
import weakref
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, Optional

import psutil
from pydantic import BaseModel, Field


class ScalingMetrics(BaseModel):
    timestamp: datetime
    load: float
    num_agents: int
    cpu_usage: float
    memory_usage: float
    queue_size: int


class ScalingConfig(BaseModel):
    scale_up_threshold: float = Field(ge=0.0, le=1.0, default=0.8)
    scale_down_threshold: float = Field(ge=0.0, le=1.0, default=0.3)
    min_agents: int = Field(ge=1, default=2)
    max_agents: int = Field(ge=1, default=10)
    cooldown_period: int = Field(ge=0, default=300)
    check_interval: int = Field(ge=1, default=60)
    scale_up_increment: int = Field(ge=1, default=1)
    scale_down_increment: int = Field(ge=1, default=1)
    metrics_retention_period: int = Field(ge=0, default=3600)


class DynamicScaling:
    def __init__(self, orchestrator, config: Optional[Dict] = None):
        self.orchestrator = weakref.proxy(orchestrator)
        self.config = ScalingConfig(**(config or {}))
        self.logger = logging.getLogger("DynamicScaling")
        self.running = False
        self.scaling_task: Optional[asyncio.Task] = None
        self.metrics_history: deque = deque(maxlen=60)  # 1 hour of minute-by-minute metrics
        self.last_scale_time = datetime.now()
        self._setup_logging()
        self._scaling_lock = asyncio.Lock()

    async def start(self):
        if self.running:
            self.logger.warning("Dynamic scaling is already running")
            return

        try:
            self.running = True
            self.scaling_task = asyncio.create_task(self._scaling_loop())
            self.logger.info("Dynamic scaling started")
        except Exception as e:
            self.running = False
            self.logger.error(f"Failed to start dynamic scaling: {str(e)}")
            raise

    async def stop(self):
        if not self.running:
            return

        try:
            self.running = False
            if self.scaling_task:
                self.scaling_task.cancel()
                try:
                    await self.scaling_task
                except asyncio.CancelledError:
                    pass
            self.logger.info("Dynamic scaling stopped")
        except Exception as e:
            self.logger.error(f"Error stopping dynamic scaling: {str(e)}")

    async def _scaling_loop(self):
        while self.running:
            try:
                async with self._scaling_lock:
                    await self._check_and_adjust_scale()
                await asyncio.sleep(self.config.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in scaling loop: {str(e)}")
                await asyncio.sleep(self.config.check_interval)

    async def _check_and_adjust_scale(self):
        try:
            current_metrics = await self._get_system_metrics()
            self._update_metrics_history(current_metrics)

            if not self._can_scale():
                return

            trend = self._analyze_load_trend()
            if trend > self.config.scale_up_threshold:
                await self._scale_up()
            elif trend < self.config.scale_down_threshold:
                await self._scale_down()

        except Exception as e:
            self.logger.error(f"Error adjusting scale: {str(e)}")

    async def _get_system_metrics(self) -> ScalingMetrics:
        try:
            agent_metrics = await asyncio.gather(*[
                agent.get_metrics()
                for agent in self.orchestrator.child_agents.values()
            ])

            num_agents = len(self.orchestrator.child_agents)
            if num_agents == 0:
                return ScalingMetrics(
                    timestamp=datetime.now(),
                    load=0.0,
                    num_agents=0,
                    cpu_usage=0.0,
                    memory_usage=0.0,
                    queue_size=0
                )

            # Calculate system-wide metrics
            total_queue_size = sum(m.get('queue_size', 0) for m in agent_metrics)
            avg_queue_util = sum(m.get('queue_utilization', 0) for m in agent_metrics) / num_agents

            # System resource metrics
            cpu_usage = psutil.cpu_percent() / 100
            memory_usage = psutil.virtual_memory().percent / 100

            # Calculate composite load
            load = (
                    0.35 * avg_queue_util +
                    0.25 * cpu_usage +
                    0.25 * memory_usage +
                    0.15 * (total_queue_size / (num_agents * 100))  # Normalize queue size
            )

            return ScalingMetrics(
                timestamp=datetime.now(),
                load=min(1.0, load),
                num_agents=num_agents,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                queue_size=total_queue_size
            )

        except Exception as e:
            self.logger.error(f"Error getting system metrics: {str(e)}")
            raise

    def _update_metrics_history(self, metrics: ScalingMetrics):
        self.metrics_history.append(metrics)

        # Clean up old metrics
        cutoff = datetime.now() - timedelta(seconds=self.config.metrics_retention_period)
        while self.metrics_history and self.metrics_history[0].timestamp < cutoff:
            self.metrics_history.popleft()

    def _analyze_load_trend(self) -> float:
        if len(self.metrics_history) < 5:
            return 0.0

        recent_metrics = list(self.metrics_history)[-5:]
        weighted_sum = sum(
            m.load * (i + 1)  # More recent metrics have higher weight
            for i, m in enumerate(recent_metrics)
        )
        weight_sum = sum(range(1, len(recent_metrics) + 1))
        return weighted_sum / weight_sum

    async def _scale_up(self):
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
                if new_agent:
                    await self.orchestrator.add_child_agent(new_agent)

            self.last_scale_time = datetime.now()
            self.logger.info(f"Scaled up by {agents_to_add} agents")

        except Exception as e:
            self.logger.error(f"Error scaling up: {str(e)}")
            raise

    async def _scale_down(self):
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
                    await self._safely_remove_agent(idle_agent)
                    removed += 1

            if removed > 0:
                self.last_scale_time = datetime.now()
                self.logger.info(f"Scaled down by {removed} agents")

        except Exception as e:
            self.logger.error(f"Error scaling down: {str(e)}")
            raise

    async def _safely_remove_agent(self, agent):
        """Safely remove an agent with proper cleanup"""
        try:
            # Wait for agent to finish current tasks
            await agent.wait_for_tasks()
            # Stop agent
            await agent.stop()
            # Remove from orchestrator
            await self.orchestrator.remove_child_agent(agent.id)
        except Exception as e:
            self.logger.error(f"Error removing agent {agent.id}: {str(e)}")
            raise

    def _can_scale(self) -> bool:
        if not self.running:
            return False
        cooldown_elapsed = (datetime.now() - self.last_scale_time).seconds > self.config.cooldown_period
        if not cooldown_elapsed:
            self.logger.debug("Scaling cooldown period not elapsed")
            return False
        return True

    async def _find_idle_agent(self):
        """Find an idle agent suitable for removal"""
        try:
            idle_agents = []
            for agent in self.orchestrator.child_agents.values():
                metrics = await agent.get_metrics()
                if (
                        agent.status == 'idle' and
                        metrics['queue_size'] == 0 and
                        metrics['active_tasks'] == 0
                ):
                    idle_agents.append((agent, metrics['success_rate']))

            if not idle_agents:
                return None

            # Remove agent with lowest success rate
            return min(idle_agents, key=lambda x: x[1])[0]

        except Exception as e:
            self.logger.error(f"Error finding idle agent: {str(e)}")
            return None

    async def get_scaling_metrics(self) -> Dict:
        """Get current scaling metrics"""
        try:
            current_metrics = await self._get_system_metrics()
            trend = self._analyze_load_trend()

            return {
                'current_metrics': current_metrics.model_dump(),
                'load_trend': trend,
                'history': [m.dict() for m in self.metrics_history],
                'last_scale_time': self.last_scale_time.isoformat(),
                'can_scale_up': len(self.orchestrator.child_agents) < self.config.max_agents,
                'can_scale_down': len(self.orchestrator.child_agents) > self.config.min_agents
            }
        except Exception as e:
            self.logger.error(f"Error getting scaling metrics: {str(e)}")
            return {}

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
