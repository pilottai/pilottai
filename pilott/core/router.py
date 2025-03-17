import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Tuple, List

from pydantic import BaseModel, Field, ConfigDict

from pilott.enums.task_e import TaskPriority


class RouterConfig(BaseModel):
    load_check_interval: int = Field(ge=1, default=5)
    max_queue_size: int = Field(gt=0, default=100)
    routing_timeout: int = Field(gt=0, default=30)
    max_retry_attempts: int = Field(ge=0, default=3)
    load_threshold: float = Field(ge=0.0, le=1.0, default=0.8)

class TaskRouter:
    """Routes tasks to appropriate agents based on various criteria"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, pilott: Any, config: Optional[Dict] = None):
        self.pilott = pilott
        self.config = RouterConfig(**(config or {}))
        self.agent_scores: Dict[str, float] = {}
        self.last_check: Dict[str, datetime] = {}
        self._router_lock = asyncio.Lock()
        self.logger = logging.getLogger("TaskRouter")

    async def route_task(self, task: Dict) -> Optional[str]:
        try:
            async with asyncio.timeout(self.config.routing_timeout):
                async with self._router_lock:
                    for attempt in range(self.config.max_retry_attempts):
                        agent_id = await self._attempt_routing(task)
                        if agent_id:
                            return agent_id
                        await asyncio.sleep(1)
                    return None
        except asyncio.TimeoutError:
            self.logger.error("Task routing timed out")
            raise RuntimeError("Task routing timed out")
        except Exception as e:
            self.logger.error(f"Routing error: {str(e)}")
            raise

    async def _attempt_routing(self, task: Dict) -> Optional[str]:
        scores = await self._calculate_agent_scores(task)
        if not scores:
            return None
        viable_agents = {
            agent_id: score
            for agent_id, score in scores.items()
            if await self._check_agent_load(agent_id) < self.config.load_threshold
        }
        if not viable_agents:
            return None
        return max(viable_agents.items(), key=lambda x: x[1])[0]

    async def _calculate_agent_scores(self, task: Dict) -> Dict[str, float]:
        current_time = datetime.now()
        scores = {}
        for agent in self.pilott.agents:
            if agent.status == "busy":
                continue
            cache_valid = (
                    agent.id in self.agent_scores and
                    agent.id in self.last_check and
                    current_time - self.last_check[agent.id] < timedelta(seconds=self.config.load_check_interval)
            )
            if cache_valid:
                scores[agent.id] = self.agent_scores[agent.id]
                continue
            try:
                base_score = await agent.evaluate_task_suitability(task)
                load_penalty = await self._calculate_load_penalty(agent)
                spec_bonus = await self._calculate_specialization_bonus(agent, task)
                perf_bonus = await self._calculate_performance_bonus(agent)
                final_score = (
                        base_score * 0.4 +
                        (1 - load_penalty) * 0.3 +
                        spec_bonus * 0.2 +
                        perf_bonus * 0.1
                )
                scores[agent.id] = final_score
                self.agent_scores[agent.id] = final_score
                self.last_check[agent.id] = current_time
            except Exception as e:
                self.logger.error(f"Error calculating score for agent {agent.id}: {str(e)}")
                continue
        return scores

    async def _calculate_load_penalty(self, agent) -> float:
        try:
            metrics = await agent.get_metrics()
            queue_load = metrics.get('queue_utilization', 1.0)
            cpu_load = metrics.get('cpu_usage', 1.0)
            memory_load = metrics.get('memory_usage', 1.0)
            return min(1.0, queue_load * 0.5 + cpu_load * 0.3 + memory_load * 0.2)
        except Exception:
            return 1.0

    async def _check_agent_load(self, agent_id: str) -> float:
        """Check current agent load"""
        try:
            agent = self.pilott.agents[agent_id]
            metrics = await agent.get_metrics()
            return metrics['queue_utilization']
        except Exception:
            return 1.0

    async def _calculate_specialization_bonus(self, agent, task: Dict) -> float:
        try:
            if not hasattr(agent, 'specializations'):
                return 0.0
            task_type = task.get('type', '')
            task_tags = set(task.get('tags', []))
            type_match = task_type in agent.specializations
            tag_matches = len(task_tags & set(agent.specializations))
            return 0.3 if type_match else (0.1 * tag_matches)
        except Exception:
            return 0.0

    async def _calculate_performance_bonus(self, agent) -> float:
        try:
            metrics = await agent.get_metrics()
            return metrics.get('success_rate', 0.5)
        except Exception:
            return 0.5

    def get_task_priority(self, task: Dict) -> TaskPriority:
        if task.get('urgent', False):
            return TaskPriority.CRITICAL
        complexity = task.get('complexity', 1)
        dependencies = len(task.get('dependencies', []))
        if complexity > 8 or dependencies > 5:
            return TaskPriority.HIGH
        elif complexity > 5 or dependencies > 3:
            return TaskPriority.MEDIUM
        else:
            return TaskPriority.LOW


class TaskDelegator:
    model_config = ConfigDict(arbitrary_types_allowed=True)
    agent: Any
    router: TaskRouter
    delegation_history: Dict[str, List[Dict]] = Field(default_factory=dict)
    max_history_per_agent: int = 1000

    async def evaluate_delegation(self, task: Dict) -> Tuple[bool, Optional[str]]:
        """Evaluate delegation with proper error handling"""
        try:
            if not self._should_delegate(task):
                return False, None

            best_agent = await self._find_best_agent(task)
            return True, best_agent.id if best_agent else None

        except Exception as e:
            self.agent.logger.error(f"Delegation evaluation failed: {str(e)}")
            return False, None

    async def _find_best_agent(self, task: Dict) -> Optional[Any]:
        """Find best agent using router's scoring"""
        try:
            agent_id = await self.router.route_task(task)
            return self.agent.child_agents.get(agent_id)
        except Exception as e:
            self.agent.logger.error(f"Error finding best agent: {str(e)}")
            return None

    def record_delegation(self, agent_id: str, task: Dict, result: Dict):
        """Record delegation with history limit"""
        if agent_id not in self.delegation_history:
            self.delegation_history[agent_id] = []

        history = self.delegation_history[agent_id]
        history.append({
            'task_id': task['id'],
            'timestamp': datetime.now().isoformat(),
            'success': result.get('status') == 'completed',
            'execution_time': result.get('execution_time'),
            'error': result.get('error')
        })

        # Trim history if needed
        if len(history) > self.max_history_per_agent:
            self.delegation_history[agent_id] = history[-self.max_history_per_agent:]
