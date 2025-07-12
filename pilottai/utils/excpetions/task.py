from pilottai.utils.excpetions.base import PilottAIException

class TaskError(PilottAIException):
    def __init__(self, message: str, task_id: str = None, **details):
        if task_id:
            details['task_id'] = task_id
        super().__init__(message, details)


class TaskValidationError(PilottAIException):
    def __init__(self, message: str, task_id: str = None, **details):
        if task_id:
            details['task_id'] = task_id
        super().__init__(f"Task validation failed: {message}", details)


class TaskExecutionError(PilottAIException):
    def __init__(self, message: str, task_id: str = None, **details):
        if task_id:
            details['task_id'] = task_id
        super().__init__(f"Task execution failed: {message}", details)
