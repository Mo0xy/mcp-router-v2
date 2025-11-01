"""
Logging configuration for the application.

Provides consistent logging setup across the application with
proper formatting and log levels.
"""

import logging
import sys
from typing import Optional
from src.config.settings import Settings


def setup_logging(settings: Optional[Settings] = None) -> None:
    """
    Setup application logging.

    Args:
        settings: Optional settings instance. If not provided, uses default.
    """
    if settings is None:
        from src.config.settings import get_settings
        settings = get_settings()

    # Get log level from settings
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Set log level for specific loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {settings.log_level}")
    logger.info(f"Application: {settings.app_name} v{settings.app_version}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Module name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)