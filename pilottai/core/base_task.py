import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field

from pilottai.enums.task_e import TaskStatus, TaskPriority
from pilottai.config.model import TaskResult


class BaseTask(BaseModel, ABC):
    """
    Abstract task class with improved status management.
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

    @abstractmethod
    async def mark_started(self, agent_id: Optional[str] = None) -> None:
        """Mark task as started with the specified agent"""
        pass

    @abstractmethod
    async def mark_completed(self, result: TaskResult) -> None:
        """Mark task as completed with the given result"""
        pass

    @abstractmethod
    async def mark_cancelled(self, reason: str = "Task cancelled") -> None:
        """Mark task as cancelled"""
        pass

    @property
    @abstractmethod
    def is_completed(self) -> bool:
        """Check if task is completed"""
        pass

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Check if task is currently active"""
        pass

    @property
    @abstractmethod
    def can_retry(self) -> bool:
        """Check if task can be retried"""
        pass

    @property
    @abstractmethod
    def is_expired(self) -> bool:
        """Check if task has expired"""
        pass

    @property
    @abstractmethod
    def duration(self) -> Optional[float]:
        """Get task duration in seconds"""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary"""
        pass

    @abstractmethod
    def copy(self, **kwargs) -> 'BaseTask':
        """Create a copy of the task with optional updates"""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseTask':
        """Create task from dictionary"""
        pass
