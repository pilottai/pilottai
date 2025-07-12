from pilottai.utils.excpetions.base import PilottAIException

class ConfigError(PilottAIException):
    def __init__(self, message: str, **details):
        super().__init__(f"Configuration error: {message}", details)


class InvalidConfigError(PilottAIException):
    def __init__(self, message: str, **details):
        super().__init__(f"Invalid configuration: {message}", details)
