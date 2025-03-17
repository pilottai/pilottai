import gzip
import json
import logging
import logging.handlers
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pilott.core.config import LogConfig


class CustomRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """Enhanced rotating file handler with compression"""

    def __init__(self, filename: str, **kwargs):
        super().__init__(filename, **kwargs)
        self.rotator = self._rotator
        self.namer = self._namer

    def _rotator(self, source: str, dest: str) -> None:
        """Compress the rotated log file"""
        with open(source, 'rb') as f_in:
            with gzip.open(f"{dest}.gz", 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(source)

    def _namer(self, default_name: str) -> str:
        """Name rotated log files"""
        return default_name + ".gz"


class JsonFormatter(logging.Formatter):
    """JSON log formatter with extra fields"""

    def __init__(self, **kwargs):
        super().__init__()
        self.extra_fields = kwargs

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'thread': record.threadName,
            'file': record.filename,
            'line': record.lineno
        }

        # Add extra fields
        log_data.update(self.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra record attributes
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


def setup_logger(
        agent: Any,
        verbose: bool = False,
        log_config: Optional[LogConfig] = None
) -> logging.Logger:
    """Setup enhanced logging system"""

    # Create logger
    logger = logging.getLogger(f"Agent_{id(agent)}")

    # Clear existing handlers
    logger.handlers.clear()

    try:
        config = log_config or LogConfig()
        log_level = getattr(logging, config.log_level.upper(), logging.INFO)
        logger.setLevel(log_level if not verbose else logging.DEBUG)

        # Create formatters
        json_formatter = JsonFormatter(
            agent_id=getattr(agent, 'id', str(id(agent))),
            agent_role=getattr(agent, 'role', 'unknown')
        )

        text_formatter = logging.Formatter(config.log_format)

        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(text_formatter)
        console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        logger.addHandler(console_handler)

        # Add file handler if configured
        if config.log_to_file:
            try:
                log_dir = Path(config.log_dir)
                log_dir.mkdir(parents=True, exist_ok=True)

                # Main log file
                main_log_path = log_dir / f"{agent.id}.log"
                file_handler = CustomRotatingFileHandler(
                    str(main_log_path),
                    when='midnight',
                    interval=1,
                    backupCount=config.backup_count,
                    encoding='utf-8'
                )
                file_handler.setFormatter(json_formatter)
                file_handler.setLevel(log_level)
                logger.addHandler(file_handler)

                # Error log file
                error_log_path = log_dir / f"{agent.id}_error.log"
                error_handler = CustomRotatingFileHandler(
                    str(error_log_path),
                    when='midnight',
                    interval=1,
                    backupCount=config.backup_count,
                    encoding='utf-8'
                )
                error_handler.setFormatter(json_formatter)
                error_handler.setLevel(logging.ERROR)
                logger.addHandler(error_handler)

                # Set up log cleanup
                setup_log_cleanup(log_dir, config.backup_count)

            except Exception as e:
                logger.warning(f"Failed to setup file logging: {str(e)}")
                # Continue with console logging only

    except Exception as e:
        # Fallback to basic logging if setup fails
        logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)
        logger.error(f"Failed to setup enhanced logging: {str(e)}")

    return logger


def setup_log_cleanup(log_dir: Path, max_backup_count: int):
    """Setup periodic log cleanup"""
    try:
        files = list(log_dir.glob("*.log.gz"))
        for file_path in files[:-max_backup_count]:
            try:
                file_path.unlink()
            except Exception:
                pass
    except Exception:
        pass


class LogContext:
    """Context manager for temporary log level changes"""

    def __init__(self, logger: logging.Logger, level: int):
        self.logger = logger
        self.level = level
        self.previous_level = logger.level

    def __enter__(self):
        self.logger.setLevel(self.level)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.previous_level)


def add_log_context(logger: logging.Logger, **context) -> None:
    """Add context to all subsequent log messages"""

    class ContextFilter(logging.Filter):
        def filter(self, record):
            for key, value in context.items():
                setattr(record, key, value)
            return True

    logger.addFilter(ContextFilter())


def create_audit_logger(base_logger: logging.Logger) -> logging.Logger:
    """Create a specialized audit logger"""
    audit_logger = logging.getLogger(f"{base_logger.name}.audit")

    # Add specialized formatter
    formatter = JsonFormatter(audit=True)

    # Add specialized handler
    handler = logging.handlers.RotatingFileHandler(
        f"audit_{base_logger.name}.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5
    )
    handler.setFormatter(formatter)
    audit_logger.addHandler(handler)

    return audit_logger
