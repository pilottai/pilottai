import logging
import os
from typing import Any
from pathlib import Path


def setup_logger(agent: Any) -> logging.Logger:
    """Setup logging for an agent with configurable file output"""
    logger = logging.getLogger(f"Agent_{id(agent)}")

    # Clear any existing handlers
    if logger.handlers:
        return logger

    # Get logging config
    log_config = agent.config.logging

    # Set log level
    log_level = getattr(logging, log_config.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter(log_config.log_format)

    # Always add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Add file handler if configured
    if log_config.log_to_file:
        try:
            # Create logs directory if it doesn't exist
            log_dir = Path(log_config.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)

            # Create log file with agent ID
            log_file = log_dir / f"{agent.id}.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            logger.debug(f"File logging enabled: {log_file}")
        except Exception as e:
            logger.warning(f"Failed to setup file logging: {str(e)}")

    return logger
