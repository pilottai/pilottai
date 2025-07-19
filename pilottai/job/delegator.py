from datetime import datetime
from typing import Dict, Optional, Any, Tuple, List
from pydantic import Field, ConfigDict

from pilottai.job.router import JobRouter

class JobDelegator:
    model_config = ConfigDict(arbitrary_types_allowed=True)
    agent: Any
    router: JobRouter
    delegation_history: Dict[str, List[Dict]] = Field(default_factory=dict)
    max_history_per_agent: int = 1000

    async def evaluate_delegation(self, job: Dict) -> Tuple[bool, Optional[str]]:
        """Evaluate delegation with proper error handling"""
        try:
            if not self._should_delegate(job):
                return False, None

            best_agent = await self._find_best_agent(job)
            return True, best_agent.id if best_agent else None

        except Exception as e:
            self.agent.logger.error(f"Delegation evaluation failed: {str(e)}")
            return False, None

    async def _find_best_agent(self, job: Dict) -> Optional[Any]:
        """Find best agent using router's scoring"""
        try:
            agent_id = await self.router.route_job(job)
            return self.agent.child_agents.get(agent_id)
        except Exception as e:
            self.agent.logger.error(f"Error finding best agent: {str(e)}")
            return None

    async def _should_delegate(self, job: Dict) -> bool:
        if job["delegate"] and job["delegate"] == True:
            return True
        return False

    def record_delegation(self, agent_id: str, job: Dict, result: Dict):
        """Record delegation with history limit"""
        if agent_id not in self.delegation_history:
            self.delegation_history[agent_id] = []

        history = self.delegation_history[agent_id]
        history.append({
            'job_id': job['id'],
            'timestamp': datetime.now().isoformat(),
            'success': result.get('status') == 'completed',
            'execution_time': result.get('execution_time'),
            'error': result.get('error')
        })

        # Trim history if needed
        if len(history) > self.max_history_per_agent:
            self.delegation_history[agent_id] = history[-self.max_history_per_agent:]
