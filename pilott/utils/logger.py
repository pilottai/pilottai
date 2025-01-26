import logging
from typing import Any, Optional
from pathlib import Path

from pilott.core import LogConfig


def setup_logger(agent: Any, verbose: bool = False, log_config: Optional[LogConfig] = None) -> logging.Logger:
    """Setup logging for an agent with configurable file output"""
    logger = logging.getLogger(f"Agent_{id(agent)}")

    if logger.handlers:
        return logger

    if log_config:
        log_level = getattr(logging, log_config.log_level.upper(), logging.INFO)
        formatter = logging.Formatter(log_config.log_format)

        # Add file handler if configured
        if log_config.log_to_file:
            try:
                log_dir = Path(log_config.log_dir)
                log_dir.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(log_dir / f"{agent.id}.log")
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except Exception as e:
                logger.warning(f"Failed to setup file logging: {str(e)}")
    else:
        log_level = logging.DEBUG if verbose else logging.INFO
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.setLevel(log_level)

    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger