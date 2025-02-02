from typing import Dict, List, Optional, Any, Set
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import uuid
import asyncio
from enum import Enum
from pathlib import Path
from contextlib import asynccontextmanager


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DELEGATED = "delegated"
    RETRY = "retry"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskResult(BaseModel):
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    resources_cleaned: bool = False
    completion_time: datetime = Field(default_factory=datetime.now)
    file_handles: Set[Any] = Field(default_factory=set, exclude=True)
    temp_files: Set[Path] = Field(default_factory=set, exclude=True)


    def __del__(self):
        if not self.resources_cleaned:
            self.cleanup_resources()

    def cleanup_resources(self):
        """Cleanup any resources used by the task result"""
        try:
            # Close file handles
            for handle in self.file_handles:
                try:
                    handle.close()
                except:
                    pass
            self.file_handles.clear()

            # Remove temp files
            for temp_file in self.temp_files:
                try:
                    temp_file.unlink()
                except:
                    pass
            self.temp_files.clear()

            self.resources_cleaned = True
        except:
            pass



class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)

    # Core execution settings
    async_execution: bool = False
    max_retries: int = Field(ge=0, default=3)
    retry_count: int = Field(ge=0, default=0)
    timeout: Optional[float] = None
    deadline: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Resource management
    file_handles: Set[Any] = Field(default_factory=set, exclude=True)
    temp_files: Set[Path] = Field(default_factory=set, exclude=True)
    locks: Dict[str, asyncio.Lock] = Field(default_factory=dict, exclude=True)

    # Additional metadata
    context: List['Task'] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    output_file: Optional[Path] = None
    result: Optional[TaskResult] = None
    complexity: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Path: str,
            set: list
        }

    def __init__(self, **data):
        super().__init__(**data)
        self._validate_dependencies()

    def __del__(self):
        """Cleanup resources on deletion"""
        try:
            self.cleanup_resources()
        except:
            pass

    def _validate_dependencies(self):
        """Validate dependencies for circular references"""
        visited = set()
        visiting = set()

        def check_cycle(task_id):
            if task_id in visiting:
                raise ValueError(f"Circular dependency detected involving task {task_id}")
            if task_id in visited:
                return
            visiting.add(task_id)
            for dep in self.dependencies:
                check_cycle(dep)
            visiting.remove(task_id)
            visited.add(task_id)

        check_cycle(self.id)

    async def acquire_lock(self, resource_name: str) -> bool:
        """Acquire a lock for a resource with timeout"""
        if not resource_name:
            raise ValueError("Resource name cannot be empty")

        if resource_name not in self.locks:
            self.locks[resource_name] = asyncio.Lock()

        try:
            await asyncio.wait_for(self.locks[resource_name].acquire(), timeout=5.0)
            return True
        except asyncio.TimeoutError:
            return False

    def release_lock(self, resource_name: str):
        """Release a resource lock safely"""
        if resource_name in self.locks and self.locks[resource_name].locked():
            try:
                self.locks[resource_name].release()
            except RuntimeError:
                pass

    @asynccontextmanager
    async def resource_lock(self, resource_name: str):
        """Context manager for resource locking"""
        if not resource_name:
            raise ValueError("Resource name cannot be empty")

        try:
            await self.acquire_lock(resource_name)
            yield
        finally:
            self.release_lock(resource_name)

    def cleanup_resources(self):
        """Cleanup all resources safely"""
        try:
            # Close file handles
            for handle in self.file_handles:
                try:
                    handle.close()
                except:
                    pass
            self.file_handles.clear()

            # Remove temp files
            for temp_file in self.temp_files:
                try:
                    temp_file.unlink()
                except:
                    pass
            self.temp_files.clear()

            # Release locks
            for resource_name in list(self.locks.keys()):
                self.release_lock(resource_name)
            self.locks.clear()

            # Cleanup result if exists
            if self.result:
                self.result.cleanup_resources()

        except Exception as e:
            # Log error but don't raise
            print(f"Error cleaning up resources: {str(e)}")

    def register_file_handle(self, handle: Any):
        """Register a file handle for cleanup"""
        if not handle:
            raise ValueError("File handle cannot be None")
        self.file_handles.add(handle)

    def register_temp_file(self, path: Path):
        """Register a temporary file for cleanup"""
        if not path:
            raise ValueError("Path cannot be None")
        self.temp_files.add(Path(path))

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v and v < datetime.now():
            raise ValueError("Deadline cannot be in the past")
        return v

    @field_validator("output_file")
    @classmethod
    def validate_output_file(cls, v: Optional[Path]) -> Optional[Path]:
        if v is None:
            return None
        v = Path(v)
        if v.exists() and not v.is_file():
            raise ValueError("Output path exists but is not a file")
        return v

    def is_expired(self) -> bool:
        """Check if task has expired"""
        if self.deadline:
            return datetime.now() > self.deadline
        return False

    def can_retry(self) -> bool:
        """Check if task can be retried"""
        return (
            self.status in [TaskStatus.FAILED, TaskStatus.TIMEOUT] and
            self.retry_count < self.max_retries and
            not self.is_expired()
        )

    def mark_started(self):
        """Mark task as started"""
        if self.status != TaskStatus.PENDING:
            raise ValueError(f"Cannot start task in {self.status} status")
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now()


    def mark_completed(self, result: TaskResult):
        """Mark task as completed"""
        if not result.success and self.can_retry():
            self.status = TaskStatus.RETRY
            self.retry_count += 1
        else:
            self.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.result = result

    def mark_failed(self, error: str):
        """Mark task as failed"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        if self.started_at:
            execution_time = (self.completed_at - self.started_at).total_seconds()
        else:
            execution_time = 0
        self.result = TaskResult(
            success=False,
            output=None,
            error=error,
            execution_time=execution_time
        )
        self.retry_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary excluding sensitive fields"""
        return self.model_dump(
            exclude={
                'file_handles',
                'temp_files',
                'locks',
                'callback',
                'on_start',
                'on_complete',
                'on_error'
            },
            exclude_none=True
        )

    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        """Custom dictionary representation"""
        d = super().model_dump(*args, **kwargs)
        # Remove callable fields as they're not serializable
        d.pop('callback', None)
        d.pop('on_start', None)
        d.pop('on_complete', None)
        d.pop('on_error', None)
        return d

    def copy(self, **kwargs) -> 'Task':
        """Create a copy with optional updates"""
        data = self.to_dict()
        data.update(kwargs)
        new_task = Task(**data)
        return new_task

    @field_validator('complexity')
    @classmethod
    def validate_complexity(cls, v):
        if not 1 <= v <= 10:
            raise ValueError("Complexity must be between 1 and 10")
        return v

    @property
    def is_overdue(self) -> bool:
        """Check if task is past its deadline"""
        if self.deadline:
            return datetime.now() > self.deadline
        return False

    @property
    def duration(self) -> Optional[float]:
        """Calculate actual task duration"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def update_status(self, status: TaskStatus, **kwargs):
        """Update task status with timestamps"""
        self.status = status
        if status == TaskStatus.IN_PROGRESS and not self.started_at:
            self.started_at = datetime.now()
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            self.completed_at = datetime.now()

        # Update any additional fields
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def add_subtask(self, subtask: 'Task'):
        """Add a subtask and update relationships"""
        subtask.parent_task_id = self.id
        self.subtasks.append(subtask.id)

    def to_prompt(self) -> str:
        """Create a prompt-friendly representation"""
        prompt = f"Task: {self.description}\n"
        if self.context:
            prompt += "\nContext:\n" + "\n".join(
                [f"- {task.description}" for task in self.context]
            )
        if self.required_skills:
            prompt += f"\nRequired Skills: {', '.join(self.required_skills)}"
        if self.tools:
            prompt += f"\nAvailable Tools: {', '.join(self.tools)}"
        return prompt
