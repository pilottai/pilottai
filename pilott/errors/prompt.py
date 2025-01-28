from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime


class PromptSecurityErrorCode(Enum):
    """Error codes for prompt security violations"""
    INTEGRITY_CHECK_FAILED = "INTEGRITY_001"
    INVALID_STRUCTURE = "STRUCTURE_001"
    SCHEMA_VALIDATION_FAILED = "SCHEMA_001"
    INTERPOLATION_ERROR = "INTERPOLATE_001"
    ENCRYPTION_ERROR = "ENCRYPT_001"
    DECRYPTION_ERROR = "DECRYPT_001"
    FILE_ACCESS_ERROR = "FILE_001"
    CACHE_ERROR = "CACHE_001"
    TEMPLATE_ERROR = "TEMPLATE_001"
    UNKNOWN_PROMPT_TYPE = "PROMPT_001"
    KEY_ERROR = "KEY_001"
    PERMISSION_DENIED = "PERM_001"


class PromptSecurityError(Exception):
    """Enhanced exception for prompt security violations"""

    def __init__(
            self,
            message: str,
            error_code: Optional[PromptSecurityErrorCode] = None,
            details: Optional[Dict[str, Any]] = None,
            *args: object
    ) -> None:
        self.timestamp = datetime.now().isoformat()
        self.error_code = error_code or PromptSecurityErrorCode.INTEGRITY_CHECK_FAILED
        self.details = details or {}

        # Enhanced error message with details
        enhanced_message = f"[{self.error_code.value}] {message}"
        if self.details:
            enhanced_message += f"\nDetails: {self.details}"

        super().__init__(enhanced_message, *args)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format"""
        return {
            "error_code": self.error_code.value,
            "message": str(self),
            "timestamp": self.timestamp,
            "details": self.details
        }

    def log_entry(self) -> str:
        """Format error for logging"""
        return (
            f"PromptSecurityError\n"
            f"Timestamp: {self.timestamp}\n"
            f"Error Code: {self.error_code.value}\n"
            f"Message: {str(self)}\n"
            f"Details: {self.details}"
        )

    @classmethod
    def integrity_error(cls, details: Optional[Dict[str, Any]] = None) -> 'PromptSecurityError':
        """Create an integrity check error"""
        return cls(
            "Prompt integrity check failed",
            PromptSecurityErrorCode.INTEGRITY_CHECK_FAILED,
            details
        )

    @classmethod
    def structure_error(cls, details: Optional[Dict[str, Any]] = None) -> 'PromptSecurityError':
        """Create a structure validation error"""
        return cls(
            "Invalid prompt structure",
            PromptSecurityErrorCode.INVALID_STRUCTURE,
            details
        )

    @classmethod
    def schema_error(cls, details: Optional[Dict[str, Any]] = None) -> 'PromptSecurityError':
        """Create a schema validation error"""
        return cls(
            "Schema validation failed",
            PromptSecurityErrorCode.SCHEMA_VALIDATION_FAILED,
            details
        )

    @classmethod
    def interpolation_error(cls, details: Optional[Dict[str, Any]] = None) -> 'PromptSecurityError':
        """Create an interpolation error"""
        return cls(
            "Template interpolation failed",
            PromptSecurityErrorCode.INTERPOLATION_ERROR,
            details
        )

    @classmethod
    def encryption_error(cls, details: Optional[Dict[str, Any]] = None) -> 'PromptSecurityError':
        """Create an encryption error"""
        return cls(
            "Prompt encryption failed",
            PromptSecurityErrorCode.ENCRYPTION_ERROR,
            details
        )

    @classmethod
    def decryption_error(cls, details: Optional[Dict[str, Any]] = None) -> 'PromptSecurityError':
        """Create a decryption error"""
        return cls(
            "Prompt decryption failed",
            PromptSecurityErrorCode.DECRYPTION_ERROR,
            details
        )

    @classmethod
    def file_access_error(cls, details: Optional[Dict[str, Any]] = None) -> 'PromptSecurityError':
        """Create a file access error"""
        return cls(
            "Prompt file access failed",
            PromptSecurityErrorCode.FILE_ACCESS_ERROR,
            details
        )

    @classmethod
    def cache_error(cls, details: Optional[Dict[str, Any]] = None) -> 'PromptSecurityError':
        """Create a cache error"""
        return cls(
            "Prompt cache operation failed",
            PromptSecurityErrorCode.CACHE_ERROR,
            details
        )

    @classmethod
    def template_error(cls, details: Optional[Dict[str, Any]] = None) -> 'PromptSecurityError':
        """Create a template error"""
        return cls(
            "Prompt template processing failed",
            PromptSecurityErrorCode.TEMPLATE_ERROR,
            details
        )

    @classmethod
    def unknown_prompt_error(cls, prompt_type: str, details: Optional[Dict[str, Any]] = None) -> 'PromptSecurityError':
        """Create an unknown prompt type error"""
        return cls(
            f"Unknown prompt type: {prompt_type}",
            PromptSecurityErrorCode.UNKNOWN_PROMPT_TYPE,
            details
        )

    @classmethod
    def key_error(cls, details: Optional[Dict[str, Any]] = None) -> 'PromptSecurityError':
        """Create a key management error"""
        return cls(
            "Prompt key management failed",
            PromptSecurityErrorCode.KEY_ERROR,
            details
        )

    @classmethod
    def permission_error(cls, details: Optional[Dict[str, Any]] = None) -> 'PromptSecurityError':
        """Create a permission error"""
        return cls(
            "Permission denied for prompt operation",
            PromptSecurityErrorCode.PERMISSION_DENIED,
            details
        )