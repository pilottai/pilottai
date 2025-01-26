from typing import Dict, Tuple, Optional, Any
from datetime import datetime
from pilott.core.status import AgentStatus


class TaskDelegator:
    def __init__(self, agent):
        self.agent = agent
        self.delegation_history = {}
        self.agent_capabilities = {}

    async def evaluate_delegation(self, task: Dict) -> Tuple[bool, Optional[str]]:
        """Evaluate if and to whom to delegate a task"""
        try:
            if not self._should_delegate(task):
                return False, None

            best_agent = await self._find_best_agent(task)
            return True, best_agent.id if best_agent else None
        except Exception as e:
            self.agent.logger.error(f"Error evaluating delegation: {str(e)}")
            return False, None

    async def _find_best_agent(self, task: Dict) -> Optional['BaseAgent']:
        """Find the best agent for delegation based on multiple criteria"""
        try:
            scores = {}
            available_agents = {
                agent_id: agent
                for agent_id, agent in self.agent.child_agents.items()
                if agent.status not in [AgentStatus.STOPPED, AgentStatus.ERROR]
            }

            if not available_agents:
                return None

            for agent_id, agent in available_agents.items():
                try:
                    # Calculate base score
                    base_score = await agent.evaluate_task_suitability(task)
                    if base_score <= 0:
                        continue

                    # Get historic performance
                    success_rate = self._get_historic_performance(agent_id, task.get('type'))

                    # Get current load
                    load_penalty = await self._calculate_load_penalty(agent)

                    # Calculate final score with weights
                    scores[agent_id] = (
                        base_score * 0.4 +          # Base suitability
                        success_rate * 0.4 -        # Historical performance
                        load_penalty * 0.2          # Current load penalty
                    )
                except Exception as e:
                    self.agent.logger.warning(
                        f"Error calculating score for agent {agent_id}: {str(e)}"
                    )
                    continue

            if not scores:
                return None

            best_agent_id = max(scores.items(), key=lambda x: x[1])[0]
            return available_agents[best_agent_id]

        except Exception as e:
            self.agent.logger.error(f"Error finding best agent: {str(e)}")
            return None

    def _get_historic_performance(self, agent_id: str, task_type: str) -> float:
        """Calculate historic performance score for an agent"""
        try:
            history = self.delegation_history.get(agent_id, {}).get(task_type, [])
            if not history:
                return 0.5  # Default score for new agents

            # Only consider recent history (last 100 tasks)
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

    def record_delegation(self, agent_id: str, task: Dict, result: Dict):
        """Record delegation result for future reference"""
        try:
            if agent_id not in self.delegation_history:
                self.delegation_history[agent_id] = {}

            task_type = task.get('type', 'default')
            if task_type not in self.delegation_history[agent_id]:
                self.delegation_history[agent_id][task_type] = []

            self.delegation_history[agent_id][task_type].append({
                'task_id': task['id'],
                'timestamp': datetime.now().isoformat(),
                'status': 'success' if result.get('status') == 'completed' else 'failure',
                'execution_time': result.get('execution_time'),
                'error': result.get('error')
            })

            # Trim history to keep only last 1000 entries per agent/type
            if len(self.delegation_history[agent_id][task_type]) > 1000:
                self.delegation_history[agent_id][task_type] = \
                    self.delegation_history[agent_id][task_type][-1000:]

        except Exception as e:
            self.agent.logger.error(f"Error recording delegation: {str(e)}")