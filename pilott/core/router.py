# pilott/core/router.py
from typing import Dict, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class TaskPriority(str, Enum):
    """Task priority levels"""
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

    # Public fields
    name: str = Field(default="TaskRouter")
    verbose: bool = Field(default=False)
    max_load_threshold: float = Field(default=0.8)
    min_score_threshold: float = Field(default=0.5)

    # Store serve reference as field
    serve_ref: Optional[Any] = Field(default=None, exclude=True)

    def route_task(self, task: Dict) -> Optional[str]:
        """Route a task to the most appropriate agent"""
        if not self.serve_ref or not self.serve_ref.agents:
            return None

        scores = self._calculate_agent_scores(task)
        if not scores:
            return None

        return max(scores.items(), key=lambda x: x[1])[0]

    def _calculate_agent_scores(self, task: Dict) -> Dict[str, float]:
        """Calculate suitability scores for available agents"""
        scores = {}
        if not self.serve_ref:
            return scores

        for agent in self.serve_ref.agents:
            if agent.status == "busy":
                continue

            # Get base suitability score
            base_score = agent.evaluate_task_suitability(task)
            if base_score < self.min_score_threshold:
                continue

            # Calculate load penalty
            load_penalty = self._calculate_load_penalty(agent)

            # Calculate specialization bonus
            specialization_bonus = self._calculate_specialization_bonus(agent, task)

            # Calculate final score
            final_score = base_score - load_penalty + specialization_bonus

            # Store score if above threshold
            if final_score >= self.min_score_threshold:
                scores[agent.id] = final_score

        return scores

    def _calculate_load_penalty(self, agent: Any) -> float:
        """Calculate penalty based on agent's current load"""
        try:
            queue_size = agent.task_queue.qsize() if hasattr(agent, 'task_queue') else 0
            if queue_size == 0:
                return 0
            return min(0.5, queue_size * 0.1)  # Max 50% penalty
        except Exception:
            return 0.0

    def _calculate_specialization_bonus(self, agent: Any, task: Dict) -> float:
        """Calculate bonus based on agent specialization"""
        try:
            # Check for task type match
            if task.get('type') in getattr(agent, 'specializations', []):
                return 0.3  # 30% bonus for specialized agents
            return 0.0
        except Exception:
            return 0.0

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
        return TaskPriority.LOW