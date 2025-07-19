import uuid
from datetime import datetime
from typing import Dict, Optional, Any
from pydantic import Field

from pilottai.enums.job_e import JobStatus, JobPriority
from pilottai.config.model import JobResult
from pilottai.core.base_job import BaseJob


class Job(BaseJob):
    """
    Job class with improved status management.
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

    async def mark_started(self, agent_id: Optional[str] = None) -> None:
        """Mark job as started with the specified agent"""
        if self.status != JobStatus.PENDING:
            raise ValueError(f"Cannot start job in {self.status} status")

        self.status = JobStatus.IN_PROGRESS
        self.agent_id = agent_id
        self.started_at = datetime.now()

    async def mark_completed(self, result: JobResult) -> None:
        """Mark job as completed with the given result"""
        self.completed_at = datetime.now()
        self.result = result

        if result.success:
            self.status = JobStatus.COMPLETED
        else:
            if hasattr(self, 'can_retry') and self.can_retry:
                self.retry_count += 1
                self.status = JobStatus.PENDING
            else:
                self.status = JobStatus.FAILED

    async def mark_cancelled(self, reason: str = "Job cancelled") -> None:
        """Mark job as cancelled"""
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.now()
        self.result = JobResult(
            success=False,
            output=None,
            error=reason,
            execution_time=self.duration or 0
        )

    @property
    def is_completed(self) -> bool:
        """Check if job is completed"""
        return self.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]

    @property
    def is_active(self) -> bool:
        """Check if job is currently active"""
        return self.status == JobStatus.IN_PROGRESS

    @property
    def can_retry(self) -> bool:
        """Check if job can be retried"""
        return (
            self.status == JobStatus.FAILED and
            self.retry_count < self.max_retries and
            not self.is_expired
        )

    @property
    def is_expired(self) -> bool:
        """Check if job has expired"""
        return bool(
            self.deadline and
            datetime.now() > self.deadline
        )

    @property
    def duration(self) -> Optional[float]:
        """Get job duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary"""
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

    def copy(self, **kwargs) -> 'Job':
        """Create a copy of the job with optional updates"""
        data = self.model_dump()
        data.update(kwargs)
        return Job(**data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        """Create job from dictionary"""
        if 'result' in data and data['result']:
            data['result'] = JobResult(**data['result'])
        return cls(**data)
