from typing import Dict, Optional, Any, Tuple
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

from pilott.core import BaseAgent


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskRouter(BaseModel):
    """Routes tasks to appropriate agents based on various criteria"""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra='allow'
    )

    pilott: Any = Field(description="Reference to parent Pilott instance")

    def route_task(self, task: Dict) -> Optional[str]:
        """
        Route a task to the most appropriate agent
        Returns agent_id or None if no suitable agent found
        """
        scores = self._calculate_agent_scores(task)
        if not scores:
            return None

        return max(scores.items(), key=lambda x: x[1])[0]

    def _calculate_agent_scores(self, task: Dict) -> Dict[str, float]:
        """Calculate suitability scores for all available agents"""
        scores = {}

        for agent in self.pilott.agents:
            if agent.status == "busy":
                continue

            base_score = agent.evaluate_task_suitability(task)
            load_penalty = self._calculate_load_penalty(agent)
            specialization_bonus = self._calculate_specialization_bonus(agent, task)

            final_score = base_score - load_penalty + specialization_bonus
            scores[agent.id] = final_score

        return scores

    def _calculate_load_penalty(self, agent) -> float:
        """Calculate penalty based on agent's current load"""
        queue_size = agent.task_queue.qsize()  # Using qsize() instead of len()
        if queue_size == 0:
            return 0
        return min(0.5, queue_size * 0.1)  # Max 50% penalty

    def _calculate_specialization_bonus(self, agent, task: Dict) -> float:
        """Calculate bonus based on agent specialization"""
        if hasattr(agent, 'specializations') and task.get('type') in agent.specializations:
            return 0.3  # 30% bonus for specialized agents
        return 0

    def get_task_priority(self, task: Dict) -> TaskPriority:
        """Determine task priority based on various factors"""
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
    def __init__(self, agent: BaseAgent):
        self.agent = agent
        self.delegation_history = {}
        self.agent_capabilities = {}

    async def evaluate_delegation(self, task: Dict) -> Tuple[bool, Optional[str]]:
        """Evaluate if and to whom to delegate"""
        if not self._should_delegate(task):
            return False, None

        best_agent = await self._find_best_agent(task)
        return True, best_agent.id if best_agent else None

    async def _find_best_agent(self, task: Dict) -> Optional[BaseAgent]:
        """Find best agent for delegation"""
        scores = {}
        for agent_id, agent in self.agent.child_agents.items():
            score = await self._calculate_agent_score(agent, task)
            scores[agent_id] = score
        return max(scores.items(), key=lambda x: x[1])[0] if scores else None