import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from logging.handlers import TimedRotatingFileHandler

from pilottai.utils.formatter import ColoredFormatter, JsonFormatter


class Logger:
    # Logging levels as class constants
    CRITICAL = 50
    FATAL = CRITICAL
    ERROR = 40
    WARNING = 30
    WARN = WARNING
    INFO = 20
    DEBUG = 10
    NOTSET = 0

    # Level to Name map
    _levelToName = {
        CRITICAL: 'CRITICAL',
        ERROR: 'ERROR',
        WARNING: 'WARNING',
        INFO: 'INFO',
        DEBUG: 'DEBUG',
        NOTSET: 'NOTSET',
    }

    # Name to Level map
    _nameToLevel = {
        'CRITICAL': CRITICAL,
        'FATAL': FATAL,
        'ERROR': ERROR,
        'WARN': WARNING,
        'WARNING': WARNING,
        'INFO': INFO,
        'DEBUG': DEBUG,
        'NOTSET': NOTSET,
    }

    _instances: Dict[str, 'Logger'] = {}

    def __init__(
            self,
            name: str = "app",
            log_dir: str = "logs",
            level: str = "INFO",
            console_output: bool = True,
            json_format: bool = False,
            max_file_size: str = "10MB",
            backup_count: int = 30
    ):
        self.name = name
        self.log_dir = Path(log_dir)
        self.level = getattr(logging, level.upper())
        self.console_output = console_output
        self.json_format = json_format
        self.max_file_size = max_file_size
        self.backup_count = backup_count

        # Create logs directory
        self.log_dir.mkdir(exist_ok=True)

        # Setup logger
        self.handlers = logging.StreamHandler(sys.stdout)
        self._setup_logger()

        # Store instance for reuse
        Logger._instances[name] = self

    def _setup_logger(self):
        self.logger = logging.getLogger(f"{self.name}")
        self.logger.setLevel(self.level)

        # Clear existing handlers to avoid duplication
        self.logger.handlers.clear()

        # Create formatters
        if self.json_format:
            formatter = JsonFormatter()
        else:
            formatter = ColoredFormatter(
                fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

        # File handler - date-wise rotation
        file_handler = TimedRotatingFileHandler(
            filename=self.log_dir / f"{self.name}.log",
            when='midnight',
            interval=1,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.suffix = '%Y-%m-%d'
        file_handler.setLevel(self.level)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Console handler (optional)
        if self.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.level)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

    def setLevel(self, level):
        self.level = level

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self._log(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with traceback"""
        kwargs['exc_info'] = True
        self._log(logging.ERROR, message, **kwargs)

    def addHandler(self, handler):
        return self.logger.addHandler(handler)

    def _log(self, level: int, message: str, **kwargs):
        """Internal logging method with context"""
        # Add context information
        extra = {
            'context': kwargs.get('context', {}),
            'agent_id': kwargs.get('agent_id'),
            'job_id': kwargs.get('job_id'),
        }

        # Remove None values
        extra = {k: v for k, v in extra.items() if v is not None}

        # Log the message
        self.logger.log(level, message, extra=extra, exc_info=kwargs.get('exc_info', False), stacklevel=3)

    def log_api_request(self, method: str, endpoint: str, status_code: int,
                        duration: float, user_id: Optional[int] = None,
                        ip_address: Optional[str] = None, **kwargs):
        """Log API request details"""
        message = f"{method} {endpoint} - {status_code} - {duration:.3f}s"

        self.info(
            message,
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration=duration,
            user_id=user_id,
            ip_address=ip_address,
            **kwargs
        )

    def log_database_query(self, query: str, duration: float, affected_rows: int = None, **kwargs):
        """Log database query performance"""
        message = f"DB Query executed in {duration:.3f}s"
        if affected_rows is not None:
            message += f" - {affected_rows} rows affected"

        self.debug(
            message,
            context={
                'query': query[:200] + '...' if len(query) > 200 else query,
                'duration': duration,
                'affected_rows': affected_rows
            },
            **kwargs
        )

    def log_user_action(self, user_id: int, action: str, details: Dict[str, Any] = None, **kwargs):
        """Log user actions for audit trail"""
        message = f"User {user_id} performed action: {action}"

        self.info(
            message,
            user_id=user_id,
            context={
                'action': action,
                'details': details or {}
            },
            **kwargs
        )

    def log_performance(self, operation: str, duration: float, **kwargs):
        """Log performance metrics"""
        level = logging.WARNING if duration > 1.0 else logging.INFO
        message = f"Performance: {operation} took {duration:.3f}s"

        self._log(
            level,
            message,
            context={'operation': operation, 'duration': duration},
            **kwargs
        )

    @classmethod
    def get_logger(cls, name: str = "app") -> 'Logger':
        """Get existing logger instance or create new one"""
        if name in cls._instances:
            return cls._instances[name]
        else:
            return cls(name=name)

    class StreamHandler(logging.StreamHandler):
        def emit(self, record):
            self.stream.write(record)
            self.stream.flush()

    class Formatter(logging.Formatter):
        def format(self, record):
            return record.getMessage()

