from pilottai.utils.excpetions.base import PilottAIException

class AgentError(PilottAIException):
    def __init__(self, message: str, agent_id: str = None, **details):
        if agent_id:
            details['agent_id'] = agent_id
        super().__init__(message, details)


class AgentInitError(PilottAIException):
    def __init__(self, message: str, agent_id: str = None, **details):
        if agent_id:
            details['agent_id'] = agent_id
        super().__init__(f"Agent initialization failed: {message}", details)


class AgentExecutionError(PilottAIException):
    def __init__(self, message: str, agent_id: str = None, task_id: str = None, **details):
        if agent_id:
            details['agent_id'] = agent_id
        if task_id:
            details['task_id'] = task_id
        super().__init__(f"Agent execution failed: {message}", details)
