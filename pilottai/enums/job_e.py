from enum import Enum

class JobPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class JobStatus(str, Enum):
    """Job execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobAssignmentType(str, Enum):
    LLM = "llm"
    SUITABILITY = "suitability"
    ROUND_ROBIN = "round_robin"
