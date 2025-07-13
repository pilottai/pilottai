import uuid
from datetime import datetime
from typing import Dict, Optional, Any
from pydantic import Field

from pilottai.enums.task_e import TaskStatus, TaskPriority
from pilottai.config.model import TaskResult
from pilottai.core.base_task import BaseTask


class Task(BaseTask):
    """
    Task class with improved status management.
    """
    # Core attributes
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = None
    description: str
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)

    # Settings
    context: Dict[str, Any] = Field(default_factory=dict)
    deadline: Optional[datetime] = None

    # Timing
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Result
    result: Optional[TaskResult] = None

    class Config:
        arbitrary_types_allowed = True

    async def mark_started(self, agent_id: Optional[str] = None) -> None:
        """Mark task as started with the specified agent"""
        if self.status != TaskStatus.PENDING:
            raise ValueError(f"Cannot start task in {self.status} status")

        self.status = TaskStatus.IN_PROGRESS
        self.agent_id = agent_id
        self.started_at = datetime.now()

    async def mark_completed(self, result: TaskResult) -> None:
        """Mark task as completed with the given result"""
        self.completed_at = datetime.now()
        self.result = result

        if result.success:
            self.status = TaskStatus.COMPLETED
        else:
            if hasattr(self, 'can_retry') and self.can_retry:
                self.retry_count += 1
                self.status = TaskStatus.PENDING
            else:
                self.status = TaskStatus.FAILED

    async def mark_cancelled(self, reason: str = "Task cancelled") -> None:
        """Mark task as cancelled"""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now()
        self.result = TaskResult(
            success=False,
            output=None,
            error=reason,
            execution_time=self.duration or 0
        )

    @property
    def is_completed(self) -> bool:
        """Check if task is completed"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]

    @property
    def is_active(self) -> bool:
        """Check if task is currently active"""
        return self.status == TaskStatus.IN_PROGRESS

    @property
    def can_retry(self) -> bool:
        """Check if task can be retried"""
        return (
                self.status == TaskStatus.FAILED and
                self.retry_count < self.max_retries and
                not self.is_expired
        )

    @property
    def is_expired(self) -> bool:
        """Check if task has expired"""
        return bool(
            self.deadline and
            datetime.now() > self.deadline
        )

    @property
    def duration(self) -> Optional[float]:
        """Get task duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary"""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "agent_id": self.agent_id,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result.to_dict() if self.result else None,
            "duration": self.duration
        }

    def copy(self, **kwargs) -> 'Task':
        """Create a copy of the task with optional updates"""
        data = self.model_dump()
        data.update(kwargs)
        return Task(**data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create task from dictionary"""
        if 'result' in data and data['result']:
            data['result'] = TaskResult(**data['result'])
        return cls(**data)
