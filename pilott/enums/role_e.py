from enum import Enum

class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"
    HYBRID = "hybrid"
    MASTER = "master"
    SUPER = "super"
    ACTION = "action"
