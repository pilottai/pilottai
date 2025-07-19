from enum import Enum

class AgentType(str, Enum):
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"
    HYBRID = "hybrid"
    MASTER = "master"
    SUPER = "super"
    ACTION = "action"
