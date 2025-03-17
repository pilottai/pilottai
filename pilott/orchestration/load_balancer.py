import asyncio
import logging
import weakref
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set, Any

import psutil
from pydantic import BaseModel, Field

from pilott.core.base_agent import BaseAgent
from pilott.enums.agent_e import AgentStatus


class LoadMetrics(BaseModel):
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    queue_size: int = 0
    active_tasks: int = 0
    total_tasks: int = 0
    error_rate: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)

class LoadBalancerConfig(BaseModel):
    check_interval: int = Field(ge=1, default=30)
    overload_threshold: float = Field(ge=0.0, le=1.0, default=0.8)
    underload_threshold: float = Field(ge=0.0, le=1.0, default=0.2)
    max_tasks_per_agent: int = Field(ge=1, default=10)
    balance_batch_size: int = Field(ge=1, default=3)
    min_load_difference: float = Field(ge=0.0, le=1.0, default=0.3)
    metrics_retention_period: int = Field(ge=0, default=3600)
    task_move_timeout: int = Field(ge=1, default=30)

class LoadBalancer:
    def __init__(self, orchestrator, config: Optional[Dict] = None):
        self.orchestrator = weakref.proxy(orchestrator)
        self.config = LoadBalancerConfig(**(config or {}))
        self.logger = logging.getLogger("LoadBalancer")
        self.running = False
        self.balancing_task: Optional[asyncio.Task] = None
        self._balance_lock = asyncio.Lock()
        self._metrics_history: Dict[str, List[LoadMetrics]] = {}
        self._monitored_agents: Set[str] = set()
        self._last_balance_time = datetime.now()
        self._safe_mode = True
        self._setup_logging()

    async def start(self):
        if self.running:
            return
        try:
            self.running = True
            self.balancing_task = asyncio.create_task(self._balancing_loop())
            self.logger.info("Load balancer started")
        except Exception as e:
            self.running = False
            self.logger.error(f"Failed to start load balancer: {str(e)}")
            raise

    async def stop(self):
        if not self.running:
            return
        try:
            self.running = False
            if self.balancing_task:
                self.balancing_task.cancel()
                try:
                    await self.balancing_task
                except asyncio.CancelledError:
                    pass
            self.logger.info("Load balancer stopped")
        except Exception as e:
            self.logger.error(f"Error stopping load balancer: {str(e)}")

    async def _balancing_loop(self):
        while self.running:
            try:
                async with self._balance_lock:
                    await self._balance_system_load()
                await asyncio.sleep(self.config.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in balancing loop: {str(e)}")
                await asyncio.sleep(self.config.check_interval)

    async def _balance_system_load(self):
        try:
            current_metrics = await self._collect_system_metrics()
            self._update_metrics_history(current_metrics)
            overloaded, underloaded = await self._analyze_agent_loads(current_metrics)
            if not overloaded or not underloaded:
                return
            await self._redistribute_tasks(overloaded, underloaded, current_metrics)
        except Exception as e:
            self.logger.error(f"Load balancing error: {str(e)}")

    async def _collect_system_metrics(self) -> Dict[str, LoadMetrics]:
        metrics = {}
        for agent in await self._get_available_agents():
            try:
                agent_metrics = await agent.get_metrics()
                system_cpu = psutil.cpu_percent(interval=1) / 100.0
                system_memory = psutil.virtual_memory().percent / 100.0

                metrics[agent.id] = LoadMetrics(
                    cpu_usage=max(system_cpu, agent_metrics.get('cpu_usage', 0.0)),
                    memory_usage=max(system_memory, agent_metrics.get('memory_usage', 0.0)),
                    queue_size=agent_metrics.get('queue_size', 0),
                    active_tasks=agent_metrics.get('active_tasks', 0),
                    total_tasks=agent_metrics.get('total_tasks', 0),
                    error_rate=1 - agent_metrics.get('success_rate', 0.0)
                )

                if metrics[agent.id].cpu_usage > self.config.overload_threshold or \
                   metrics[agent.id].memory_usage > self.config.overload_threshold:
                    await self._handle_overload(agent.id)

            except Exception as e:
                self.logger.error(f"Error collecting metrics for agent {agent.id}: {str(e)}")
        return metrics

    async def _handle_overload(self, agent_id: str):
        try:
            agent = self.orchestrator.child_agents[agent_id]
            await agent.pause_task_acceptance()
            self.logger.warning(f"Agent {agent_id} paused due to resource overload")
        except Exception as e:
            self.logger.error(f"Error handling overload for agent {agent_id}: {str(e)}")

    def _update_metrics_history(self, metrics: Dict[str, LoadMetrics]):
        current_time = datetime.now()
        retention_time = current_time - timedelta(seconds=self.config.metrics_retention_period)

        for agent_id, metric in metrics.items():
            if agent_id not in self._metrics_history:
                self._metrics_history[agent_id] = []

            self._metrics_history[agent_id].append(metric)
            self._metrics_history[agent_id] = [
                m for m in self._metrics_history[agent_id]
                if m.timestamp > retention_time
            ]

    async def _analyze_agent_loads(
            self,
            current_metrics: Dict[str, LoadMetrics]
    ) -> Tuple[List[str], List[str]]:
        overloaded = []
        underloaded = []

        for agent_id, metrics in current_metrics.items():
            load_trend = self._calculate_load_trend(agent_id)
            current_load = self._calculate_composite_load(metrics)

            if current_load > self.config.overload_threshold and load_trend > 0:
                overloaded.append(agent_id)
            elif current_load < self.config.underload_threshold and load_trend < 0:
                underloaded.append(agent_id)

        return overloaded, underloaded

    def _calculate_load_trend(self, agent_id: str) -> float:
        if agent_id not in self._metrics_history:
            return 0.0

        history = self._metrics_history[agent_id][-5:]
        if len(history) < 2:
            return 0.0

        loads = [self._calculate_composite_load(m) for m in history]
        return (loads[-1] - loads[0]) / len(loads)

    def _calculate_composite_load(self, metrics: LoadMetrics) -> float:
        return (
            0.3 * metrics.cpu_usage +
            0.3 * metrics.memory_usage +
            0.2 * (metrics.queue_size / self.config.max_tasks_per_agent) +
            0.2 * metrics.error_rate
        )

    async def _redistribute_tasks(
            self,
            overloaded: List[str],
            underloaded: List[str],
            current_metrics: Dict[str, LoadMetrics]
    ):
        for over_agent_id in overloaded:
            try:
                moveable_tasks = await self._get_moveable_tasks(over_agent_id)
                moves_made = 0

                moveable_tasks.sort(key=lambda x: x.get('priority', 0), reverse=True)

                for task in moveable_tasks:
                    if moves_made >= self.config.balance_batch_size:
                        break

                    best_agent_id = await self._find_best_agent(
                        task,
                        underloaded,
                        current_metrics
                    )

                    if best_agent_id:
                        try:
                            async with asyncio.timeout(self.config.task_move_timeout):
                                await self._move_task(task, over_agent_id, best_agent_id)
                                moves_made += 1
                        except asyncio.TimeoutError:
                            self.logger.error(f"Task move timed out for task {task['id']}")
                        except Exception as e:
                            self.logger.error(f"Failed to move task {task['id']}: {str(e)}")

                if moves_made > 0:
                    self._last_balance_time = datetime.now()
                    self.logger.info(f"Moved {moves_made} tasks from agent {over_agent_id}")

            except Exception as e:
                self.logger.error(f"Error redistributing tasks for agent {over_agent_id}: {str(e)}")

    async def _move_task(self, task: Dict, from_agent_id: str, to_agent_id: str):
        lock_acquired = False
        try:
            from_agent = self.orchestrator.child_agents[from_agent_id]
            to_agent = self.orchestrator.child_agents[to_agent_id]

            task['locked'] = True
            lock_acquired = True

            if self._safe_mode:
                # Save task state before moving
                task_backup = task.copy()

            await from_agent.remove_task(task['id'])
            await to_agent.add_task(task)

            task['moved_at'] = datetime.now().isoformat()
            task['moved_from'] = from_agent_id
            task['moved_to'] = to_agent_id

            self.logger.info(f"Moved task {task['id']} from {from_agent_id} to {to_agent_id}")

        except Exception as e:
            self.logger.error(f"Task movement failed: {str(e)}")
            if lock_acquired and self._safe_mode:
                try:
                    await from_agent.add_task(task_backup)
                except Exception as restore_error:
                    self.logger.error(f"Failed to restore task {task['id']}: {str(restore_error)}")
            raise
        finally:
            task['locked'] = False

    async def _get_moveable_tasks(self, agent_id: str) -> List[Dict]:
        try:
            agent = self.orchestrator.child_agents[agent_id]
            return [task for task in agent.tasks.values() if self._is_task_moveable(task)]
        except Exception as e:
            self.logger.error(f"Error getting moveable tasks: {str(e)}")
            return []

    def _is_task_moveable(self, task: Dict) -> bool:
        return (
            task.get('status') == 'pending' and
            not task.get('locked', False) and
            not task.get('unmoveable', False)
        )

    async def _find_best_agent(
            self,
            task: Dict,
            candidates: List[str],
            current_metrics: Dict[str, LoadMetrics]
    ) -> Optional[str]:
        best_agent_id = None
        best_score = float('-inf')

        for agent_id in candidates:
            try:
                agent = self.orchestrator.child_agents[agent_id]
                if not await self._can_accept_task(agent, current_metrics[agent_id]):
                    continue

                score = await self._calculate_agent_suitability(agent, task, current_metrics[agent_id])

                if score > best_score:
                    best_score = score
                    best_agent_id = agent_id

            except Exception as e:
                self.logger.error(f"Error calculating suitability for agent {agent_id}: {str(e)}")

        return best_agent_id

    async def _can_accept_task(
            self,
            agent: Any,
            metrics: LoadMetrics
    ) -> bool:
        """Check if agent can accept new tasks"""
        return (
                agent.status != 'stopped' and
                metrics.queue_size < self.config.max_tasks_per_agent and
                self._calculate_composite_load(metrics) < self.config.overload_threshold
        )

    async def _calculate_agent_suitability(
            self,
            agent: Any,
            task: Dict,
            metrics: LoadMetrics
    ) -> float:
        """Calculate comprehensive agent suitability score"""
        try:
            # Base capability score
            base_score = await agent.evaluate_task_suitability(task)

            # Load penalty
            load_score = 1 - self._calculate_composite_load(metrics)

            # Performance score
            perf_score = 1 - metrics.error_rate

            # Resource availability
            resource_score = 1 - max(metrics.cpu_usage, metrics.memory_usage)

            # Calculate weighted score
            return (
                    base_score * 0.4 +
                    load_score * 0.3 +
                    perf_score * 0.2 +
                    resource_score * 0.1
            )

        except Exception as e:
            self.logger.error(f"Error calculating agent suitability: {str(e)}")
            return float('-inf')

    async def get_metrics(self) -> Dict[str, Any]:
        return {
            "active_agents": len(await self._get_available_agents()),
            "overloaded_agents": len([
                agent_id for agent_id, metrics in (await self._collect_system_metrics()).items()
                if self._calculate_composite_load(metrics) > self.config.overload_threshold
            ]),
            "underloaded_agents": len([
                agent_id for agent_id, metrics in (await self._collect_system_metrics()).items()
                if self._calculate_composite_load(metrics) < self.config.underload_threshold
            ]),
            "last_balance_time": self._last_balance_time.isoformat(),
            "metrics_history": {
                agent_id: [m.model_dump() for m in history]
                for agent_id, history in self._metrics_history.items()
            }
        }

    def _setup_logging(self):
        self.logger.setLevel(logging.DEBUG if self.orchestrator.verbose else logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(handler)

    async def _get_available_agents(self) -> List[BaseAgent]:
        return [
            agent for agent in self.orchestrator.child_agents.values()
            if agent.status != AgentStatus.STOPPED
        ]


    async def _calculate_agent_load(self, agent: BaseAgent) -> float:
        """Calculate comprehensive load for an agent"""
        try:
            metrics = await agent.get_metrics()
            # Calculate different types of load
            task_load = metrics['total_tasks'] / self.config.max_tasks_per_agent
            queue_load = metrics['queue_utilization']
            error_rate = 1 - metrics['success_rate']  # Convert success rate to error rate

            # Weighted average with error rate penalty
            base_load = (
                    0.4 * task_load +
                    0.4 * queue_load +
                    0.2 * error_rate
            )
            return min(1.0, base_load)  # Cap at 1.0

        except Exception as e:
            self.logger.error(f"Error calculating agent load: {str(e)}")
            return 0.0
