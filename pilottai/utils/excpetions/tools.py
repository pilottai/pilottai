from pilottai.utils.excpetions.base import PilottAIException

class ToolError(PilottAIException):
    def __init__(self, message: str, tool_name: str = None, **details):
        if tool_name:
            details['tool_name'] = tool_name
        super().__init__(message, details)


class ToolNotFoundError(PilottAIException):
    def __init__(self, message: str, tool_name: str = None, **details):
        if tool_name:
            details['tool_name'] = tool_name
        super().__init__(f"Tool not found: {message}", details)


class ToolExecutionError(PilottAIException):
    def __init__(self, message: str, tool_name: str = None, **details):
        if tool_name:
            details['tool_name'] = tool_name
        super().__init__(f"Tool execution failed: {message}", details)
