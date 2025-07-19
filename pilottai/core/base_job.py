import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field

from pilottai.enums.job_e import JobStatus, JobPriority
from pilottai.config.model import JobResult


class BaseJob(BaseModel, ABC):
    """
    Abstract job class with improved status management.
    """
    # Core attributes
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = None
    description: str
    status: JobStatus = Field(default=JobStatus.PENDING)
    priority: JobPriority = Field(default=JobPriority.MEDIUM)

    # Settings
    context: Dict[str, Any] = Field(default_factory=dict)
    deadline: Optional[datetime] = None

    # Timing
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Result
    result: Optional[JobResult] = None

    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    async def mark_started(self, agent_id: Optional[str] = None) -> None:
        """Mark job as started with the specified agent"""
        pass

    @abstractmethod
    async def mark_completed(self, result: JobResult) -> None:
        """Mark job as completed with the given result"""
        pass

    @abstractmethod
    async def mark_cancelled(self, reason: str = "jon cancelled") -> None:
        """Mark job as cancelled"""
        pass

    @property
    @abstractmethod
    def is_completed(self) -> bool:
        """Check if job is completed"""
        pass

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Check if job is currently active"""
        pass

    @property
    @abstractmethod
    def can_retry(self) -> bool:
        """Check if job can be retried"""
        pass

    @property
    @abstractmethod
    def is_expired(self) -> bool:
        """Check if job has expired"""
        pass

    @property
    @abstractmethod
    def duration(self) -> Optional[float]:
        """Get job duration in seconds"""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary"""
        pass

    @abstractmethod
    def copy(self, **kwargs) -> 'BaseJob':
        """Create a copy of the job with optional updates"""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseJob':
        """Create job from dictionary"""
        pass
