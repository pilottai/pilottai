from enum import Enum

class AgentStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    WAITING = "waiting"
    ERROR = "error"
    STOPPED = "stopped"