from pilottai.utils.excpetions.base import PilottAIException

class LLMError(PilottAIException):
    def __init__(self, message: str, model_name: str = None, **details):
        if model_name:
            details['model_name'] = model_name
        super().__init__(f"LLM error: {message}", details)


class LLMConnectionError(PilottAIException):
    def __init__(self, message: str, model_name: str = None, **details):
        if model_name:
            details['model_name'] = model_name
        super().__init__(f"LLM connection failed: {message}", details)


class LLMAPIError(PilottAIException):
    def __init__(self, message: str, model_name: str = None, status_code: int = None, **details):
        if model_name:
            details['model_name'] = model_name
        if status_code:
            details['status_code'] = status_code
        super().__init__(f"LLM API error: {message}", details)
