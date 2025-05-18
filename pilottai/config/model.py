from typing import Optional, Dict, Any, Set, List
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

from pilottai.enums.health_e import HealthStatus

class MemoryEntry(BaseModel):
    """Enhanced memory entry with task awareness"""
    text: str
    entry_type: str  # 'task', 'context', 'result', etc.
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    tags: Set[str] = Field(default_factory=set)
    priority: int = Field(ge=0, default=1)
    task_id: Optional[str] = None
    agent_id: Optional[str] = None


class DelegationMetrics(BaseModel):
    success_count: int = 0
    failure_count: int = 0
    total_execution_time: float = 0
    avg_execution_time: float = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    error_types: Dict[str, int] = Field(default_factory=dict)


class CacheEntry(BaseModel):
    value: Any
    timestamp: datetime
    ttl: int
    access_count: int = 0
    last_access: datetime = Field(default_factory=datetime.now)


class KnowledgeSource(BaseModel):
    name: str
    type: str
    connection: Dict[str, Any]
    last_access: datetime = Field(default_factory=datetime.now)
    access_count: int = 0
    error_count: int = 0
    is_connected: bool = False
    max_retries: int = 3
    retry_delay: int = 5
    timeout: int = 30


class MemoryItem(BaseModel):
    """Enhanced memory item model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    tags: Set[str] = Field(default_factory=set)
    priority: int = Field(ge=0, default=0)
    expires_at: Optional[datetime] = None
    version: int = 1

    def is_expired(self) -> bool:
        return self.expires_at and datetime.now() > self.expires_at


class ScalingMetrics(BaseModel):
    timestamp: datetime
    load: float = Field(ge=0.0, le=1.0)
    num_agents: int = Field(ge=0)
    cpu_usage: float = Field(ge=0.0, le=1.0)
    memory_usage: float = Field(ge=0.0, le=1.0)
    queue_size: int = Field(ge=0)


class AgentHealth(BaseModel):
    status: HealthStatus
    last_heartbeat: datetime
    resource_usage: float
    error_count: int
    recovery_attempts: int
    stuck_tasks: List[str]
    last_error: Optional[str] = None

class LoadMetrics(BaseModel):
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    queue_size: int = 0
    active_tasks: int = 0
    total_tasks: int = 0
    error_rate: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)

class ToolMetrics(BaseModel):
    usage_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_execution_time: float = 0
    avg_execution_time: float = 0
    last_execution: Optional[datetime] = None
    last_error: Optional[str] = None
    error_types: Dict[str, int] = Field(default_factory=dict)

class TaskResult(BaseModel):
    """Result of task execution"""
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    completion_time: datetime = Field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
            "completion_time": self.completion_time.isoformat()
        }

class ToolError(Exception):
    """Base class for tool errors"""
    pass

class ToolTimeoutError(ToolError):
    """Tool execution timeout error"""
    pass

class ToolPermissionError(ToolError):
    """Tool permission error"""
    pass

class ToolValidationError(ToolError):
    """Tool input validation error"""
    pass
