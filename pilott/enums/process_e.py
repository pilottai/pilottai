from enum import Enum

class ProcessType(str, Enum):
    """Processing type for task execution"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"
    HYBRID = "hybrid"
