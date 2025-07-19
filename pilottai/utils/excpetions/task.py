from pilottai.utils.excpetions.base import PilottAIException

class JobError(PilottAIException):
    def __init__(self, message: str, job_id: str = None, **details):
        if job_id:
            details['job_id'] = job_id
        super().__init__(message, details)


class JobValidationError(PilottAIException):
    def __init__(self, message: str, job_id: str = None, **details):
        if job_id:
            details['job_id'] = job_id
        super().__init__(f"Job validation failed: {message}", details)


class JobExecutionError(PilottAIException):
    def __init__(self, message: str, job_id: str = None, **details):
        if job_id:
            details['job_id'] = job_id
        super().__init__(f"Job execution failed: {message}", details)
