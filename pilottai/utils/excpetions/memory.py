from pilottai.utils.excpetions.base import PilottAIException

class MemoryError(PilottAIException):
    def __init__(self, message: str, **details):
        super().__init__(f"Memory error: {message}", details)


class MemoryStorageError(PilottAIException):
    def __init__(self, message: str, **details):
        super().__init__(f"Memory storage failed: {message}", details)
