import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, Any, List

from pilottai.config.model import DelegationMetrics
from pilottai.utils.logger import Logger


class JobDelegator:
    def __init__(self, agent):
        self.agent = agent
        self.delegation_history: Dict[str, List[Dict]] = defaultdict(list)
        self.agent_metrics: Dict[str, DelegationMetrics] = {}
        self.active_delegations: Dict[str, Dict] = {}
        self.logger = Logger(f"JobDelegator_{agent.id}")
        self._delegation_lock = asyncio.Lock()
        self.MAX_HISTORY_PER_AGENT = 1000
        self.HISTORY_CLEANUP_INTERVAL = 3600
        self._last_cleanup = datetime.now()
        self._cleanup_job = None

    async def start(self):
        #TODO
        self._cleanup_job = asyncio.create_job(self._periodic_cleanup())

    async def stop(self):
        if self._cleanup_job:
            self._cleanup_job.cancel()
            try:
                await self._cleanup_job
            except asyncio.CancelledError:
                pass

    async def evaluate_delegation(self, job: Dict) -> Tuple[bool, Optional[str]]:
        try:
            async with self._delegation_lock:
                if not await self._should_delegate(job):
                    return False, None

                best_agent = await self._find_best_agent(job)
                if best_agent:
                    self.active_delegations[job['id']] = {
                        'agent_id': best_agent.id,
                        'started_at': datetime.now(),
                        'job': job
                    }
                    return True, best_agent.id
                return False, None
        except Exception as e:
            self.logger.error(f"Delegation evaluation failed: {str(e)}")
            return False, None

    async def _find_best_agent(self, job: Dict) -> Optional[Any]:
        try:
            scores = {}
            available_agents = self._get_available_agents()

            async with asyncio.timeout(10):  # 10 second timeout
                for agent_id, agent in available_agents.items():
                    try:
                        if not await self._can_accept_job(agent):
                            continue

                        score = await self._calculate_total_score(agent, job)
                        if score > 0:
                            scores[agent_id] = score

                    except Exception as e:
                        self.logger.error(f"Error calculating score for agent {agent_id}: {str(e)}")
                        continue

                if not scores:
                    return None

                best_agent_id = max(scores.items(), key=lambda x: x[1])[0]
                return available_agents[best_agent_id]

        except asyncio.TimeoutError:
            self.logger.error("Agent selection timed out")
            return None
        except Exception as e:
            self.logger.error(f"Error finding best agent: {str(e)}")
            return None

    async def _calculate_total_score(self, agent: Any, job: Dict) -> float:
        try:
            base_score = await agent.evaluate_job_suitability(job)
            metrics = await agent.get_metrics()

            load_score = 1 - metrics.get('queue_utilization', 0)
            success_rate = metrics.get('success_rate', 0.5)
            error_rate = 1 - success_rate

            resource_score = 1 - max(
                metrics.get('cpu_usage', 0),
                metrics.get('memory_usage', 0)
            )

            return (
                    base_score * 0.4 +
                    load_score * 0.3 +
                    (1 - error_rate) * 0.2 +
                    resource_score * 0.1
            )
        except Exception:
            return 0.0

    async def _calculate_base_score(self, agent: Any, job: Dict) -> float:
        """Calculate base suitability score"""
        try:
            capabilities_match = await agent.evaluate_job_suitability(job)
            specialization_bonus = 0.2 if job.get('type') in getattr(agent, 'specializations', []) else 0
            return capabilities_match + specialization_bonus
        except Exception:
            return 0.0

    def _calculate_performance_score(self, agent_id: str, job: Dict) -> float:
        """Calculate performance score based on history"""
        try:
            metrics = self.agent_metrics.get(agent_id)
            if not metrics:
                return 0.5

            total_jobs = metrics.success_count + metrics.failure_count
            if total_jobs == 0:
                return 0.5

            success_rate = metrics.success_count / total_jobs
            similar_job_bonus = self._get_similar_job_performance(agent_id, job)
            return 0.7 * success_rate + 0.3 * similar_job_bonus
        except Exception:
            return 0.5

    async def _calculate_load_score(self, agent: Any) -> float:
        """Calculate current load score"""
        try:
            metrics = await agent.get_metrics()
            return metrics.get('queue_utilization', 1.0)
        except Exception:
            return 1.0

    async def _calculate_resource_score(self, agent: Any) -> float:
        """Calculate resource availability score"""
        try:
            metrics = await agent.get_metrics()
            cpu_usage = metrics.get('cpu_usage', 1.0)
            memory_usage = metrics.get('memory_usage', 1.0)
            return 1 - ((cpu_usage + memory_usage) / 2)
        except Exception:
            return 0.0

    def _get_similar_job_performance(self, agent_id: str, job: Dict) -> float:
        """Calculate performance for similar job"""
        try:
            similar_jobs = [
                entry for entry in self.delegation_history[agent_id]
                if self._is_similar_job(entry['job'], job)
            ]

            if not similar_jobs:
                return 0.5

            success_count = sum(1 for job in similar_jobs if job.get('success', False))
            return success_count / len(similar_jobs)

        except Exception:
            return 0.5

    def _is_similar_job(self, job1: Dict, job2: Dict) -> bool:
        """Compare job similarity"""
        return (
                job1.get('type') == job2.get('type') or
                bool(set(job1.get('tags', [])) & set(job2.get('tags', [])))
        )

    async def record_delegation(self, agent_id: str, job: Dict, result: Dict):
        try:
            async with self._delegation_lock:
                entry = {
                    'job_id': job['id'],
                    'job': job,
                    'timestamp': datetime.now().isoformat(),
                    'success': result.get('status') == 'completed',
                    'execution_time': result.get('execution_time', 0),
                    'error': result.get('error'),
                    'error_type': result.get('error_type')
                }

                self.delegation_history[agent_id].append(entry)
                if len(self.delegation_history[agent_id]) > self.MAX_HISTORY_PER_AGENT:
                    self.delegation_history[agent_id].pop(0)

                metrics = self.agent_metrics.setdefault(agent_id, DelegationMetrics())

                if entry['success']:
                    metrics.success_count += 1
                    metrics.last_success = datetime.now()
                else:
                    metrics.failure_count += 1
                    metrics.last_failure = datetime.now()
                    error_type = entry.get('error_type', 'unknown')
                    metrics.error_types[error_type] = metrics.error_types.get(error_type, 0) + 1

                total_jobs = metrics.success_count + metrics.failure_count
                metrics.total_execution_time += entry['execution_time']
                metrics.avg_execution_time = metrics.total_execution_time / total_jobs

                # Remove completed delegation
                self.active_delegations.pop(job['id'], None)

        except Exception as e:
            self.logger.error(f"Error recording delegation: {str(e)}")

    def get_agent_metrics(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive agent metrics"""
        try:
            metrics = self.agent_metrics.get(agent_id)
            if not metrics:
                return None

            return {
                'success_rate': metrics.success_count / (metrics.success_count + metrics.failure_count)
                if (metrics.success_count + metrics.failure_count) > 0 else 0,
                'avg_execution_time': metrics.avg_execution_time,
                'total_jobs': metrics.success_count + metrics.failure_count,
                'last_success': metrics.last_success,
                'last_failure': metrics.last_failure,
                'error_distribution': metrics.error_types
            }
        except Exception:
            return None



    def _get_historic_performance(self, agent_id: str, job_type: str) -> float:
        """Calculate historic performance score for an agent"""
        try:
            history = self.delegation_history.get(agent_id, {}).get(job_type, [])
            if not history:
                return 0.5  # Default score for new agents

            # Only consider recent history (last 100 job)
            recent_history = history[-100:]
            successes = sum(1 for result in recent_history
                          if result.get('status') == 'success')
            return successes / len(recent_history)

        except Exception as e:
            self.agent.logger.error(
                f"Error calculating historic performance for {agent_id}: {str(e)}"
            )
            return 0.5

    async def _calculate_load_penalty(self, agent) -> float:
        """Calculate load penalty based on agent metrics"""
        try:
            metrics = await agent.get_metrics()
            return min(1.0, metrics['queue_utilization'])  # Cap at 1.0
        except Exception as e:
            self.agent.logger.error(
                f"Error calculating load penalty for {agent.id}: {str(e)}"
            )
            return 1.0  # Maximum penalty on error

    async def _periodic_cleanup(self):
        while True:
            try:
                await asyncio.sleep(self.HISTORY_CLEANUP_INTERVAL)
                await self._cleanup_old_history()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Cleanup error: {str(e)}")

    async def _cleanup_old_history(self):
        try:
            async with self._delegation_lock:
                current_time = datetime.now()
                cutoff_time = current_time - timedelta(hours=24)

                for agent_id in list(self.delegation_history.keys()):
                    history = self.delegation_history[agent_id]
                    self.delegation_history[agent_id] = [
                                                            entry for entry in history
                                                            if datetime.fromisoformat(entry['timestamp']) > cutoff_time
                                                        ][-self.MAX_HISTORY_PER_AGENT:]

                # Clean up stale delegations
                stale_jobs = [
                    job_id for job_id, info in self.active_delegations.items()
                    if current_time - info['started_at'] > timedelta(hours=1)
                ]
                for job_id in stale_jobs:
                    self.active_delegations.pop(job_id)

                self._last_cleanup = current_time

        except Exception as e:
            self.logger.error(f"Error cleaning up history: {str(e)}")

    def _get_available_agents(self) -> Dict[str, Any]:
        return {
            agent_id: agent
            for agent_id, agent in self.agent.child_agents.items()
            if agent.status not in ['stopped', 'error'] and
               len([d for d in self.active_delegations.values() if d['agent_id'] == agent_id]) < getattr(agent, 'max_concurrent_jobs',5)
        }

    async def _can_accept_job(self, agent: Any) -> bool:
        try:
            metrics = await agent.get_metrics()
            return (
                    agent.status not in ['stopped', 'error'] and
                    metrics['queue_utilization'] < 0.8 and
                    metrics['cpu_usage'] < 0.8 and
                    metrics['memory_usage'] < 0.8
            )
        except Exception:
            return False

    async def _should_delegate(self, job: Dict) -> bool:
        try:
            if not self.agent.config.allow_delegation:
                return False

            metrics = await self.agent.get_metrics()
            if metrics['queue_utilization'] > 0.8:
                return True

            if job.get('complexity', 1) > self.agent.config.max_job_complexity:
                return True

            if job.get('required_capabilities'):
                missing_capabilities = set(job['required_capabilities']) - set(self.agent.config.required_capabilities)
                if missing_capabilities:
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Error checking delegation: {str(e)}")
            return False

    async def get_metrics(self) -> Dict[str, Any]:
        return {
            'active_delegations': len(self.active_delegations),
            'agent_metrics': {
                agent_id: metrics.model_dump()
                for agent_id, metrics in self.agent_metrics.items()
            },
            'history_size': sum(len(h) for h in self.delegation_history.values()),
            'last_cleanup': self._last_cleanup.isoformat()
        }
