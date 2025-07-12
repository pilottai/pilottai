from typing import Any, Dict, Optional


class PilottAIException(Exception):
    """Base exception for PilottAI."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
        print(f"❌ {self.__class__.__name__}: {self.message}")
        if self.details:
            print(f"   Details: {self.details}")

def handle_errors(func):
    """Catch and convert errors to PilottAI exceptions."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except PilottAIException:
            raise
        except Exception as e:
            raise PilottAIException(f"Error in {func.__name__}: {str(e)}")
    return wrapper
