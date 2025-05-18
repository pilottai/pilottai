from enum import Enum

class ToolStatus(str, Enum):
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    DISABLED = "disabled"