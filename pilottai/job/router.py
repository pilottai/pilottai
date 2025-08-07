import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

from pydantic import ConfigDict

from pilottai.core.base_config import RouterConfig
from pilottai.enums.job_e import JobPriority
from pilottai.utils.logger import Logger


class JobRouter:
    """Routes job to appropriate agents based on various criteria"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, pilott: Any, config: Optional[Dict] = None):
        self.pilott = pilott
        self.config = RouterConfig(**(config or {}))
        self.agent_scores: Dict[str, float] = {}
        self.last_check: Dict[str, datetime] = {}
        self._router_lock = asyncio.Lock()
        self.logger = Logger("JobRouter")

    async def route_job(self, job: Dict) -> Optional[str]:
        try:
            return await asyncio.wait_for(
                self._route_job_internal(job),
                timeout=self.config.routing_timeout
            )
        except asyncio.TimeoutError:
            self.logger.error("Job routing timed out")
            raise RuntimeError("Job routing timed out")
        except Exception as e:
            self.logger.error(f"Routing error: {str(e)}")
            raise

    async def _route_job_internal(self, job: Dict) -> Optional[str]:
        async with self._router_lock:
            for attempt in range(self.config.max_retry_attempts):
                agent_id = await self._attempt_routing(job)
                if agent_id:
                    return agent_id
                await asyncio.sleep(1)
            return None

    async def _attempt_routing(self, job: Dict) -> Optional[str]:
        scores = await self._calculate_agent_scores(job)
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

    async def _calculate_agent_scores(self, job: Dict) -> Dict[str, float]:
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
                base_score = await agent.evaluate_job_suitability(job)
                load_penalty = await self._calculate_load_penalty(agent)
                spec_bonus = await self._calculate_specialization_bonus(agent, job)
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

    async def _calculate_specialization_bonus(self, agent, job: Dict) -> float:
        try:
            if not hasattr(agent, 'specializations'):
                return 0.0
            job_type = job.get('type', '')
            job_tags = set(job.get('tags', []))
            type_match = job_type in agent.specializations
            tag_matches = len(job_tags & set(agent.specializations))
            return 0.3 if type_match else (0.1 * tag_matches)
        except Exception:
            return 0.0

    async def _calculate_performance_bonus(self, agent) -> float:
        try:
            metrics = await agent.get_metrics()
            return metrics.get('success_rate', 0.5)
        except Exception:
            return 0.5

    def get_job_priority(self, job: Dict) -> JobPriority:
        if job.get('urgent', False):
            return JobPriority.CRITICAL
        complexity = job.get('complexity', 1)
        dependencies = len(job.get('dependencies', []))
        if complexity > 8 or dependencies > 5:
            return JobPriority.HIGH
        elif complexity > 5 or dependencies > 3:
            return JobPriority.MEDIUM
        else:
            return JobPriority.LOW
