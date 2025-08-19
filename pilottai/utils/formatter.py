import logging
from datetime import datetime
import json
import traceback

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""

    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',  # Cyan
        'INFO': '\033[32m',  # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',  # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m',  # Reset
        'OUTPUT': '\033[37m',    # White
    }

    def format(self, record):
        # Add color to levelname
        if hasattr(record, 'levelname'):
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"

        # Format the message
        formatted = super().format(record)

        # Add context information if present
        if hasattr(record, 'context') and record.context:
            context_str = json.dumps(record.context, indent=2)
            formatted += f"\n📋 Context: {context_str}"

        return formatted


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def custom_serializer(self, obj):
        if hasattr(obj, "to_dict"):  # if your JobResult has to_dict
            return obj.to_dict()
        if hasattr(obj, "__dict__"):  # fallback: use its __dict__
            return obj.__dict__
        if isinstance(obj, datetime):  # handle datetime cleanly
            return obj.isoformat()
        return str(obj)  # last resort

    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'thread_name': record.threadName
        }

        # Add exception information
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }

        json_output = json.dumps(log_entry, ensure_ascii=False, indent=2, default=self.custom_serializer)
        return json_output
