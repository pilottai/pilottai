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
        'RESET': '\033[0m'  # Reset
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

        # Add context information
        if hasattr(record, 'context'):
            log_entry['context'] = record.context

        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id

        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id

        if hasattr(record, 'ip_address'):
            log_entry['ip_address'] = record.ip_address

        if hasattr(record, 'endpoint'):
            log_entry['endpoint'] = record.endpoint

        if hasattr(record, 'method'):
            log_entry['method'] = record.method

        if hasattr(record, 'duration'):
            log_entry['duration'] = record.duration

        if hasattr(record, 'status_code'):
            log_entry['status_code'] = record.status_code

        # Add exception information
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }

        return json.dumps(log_entry, ensure_ascii=False)