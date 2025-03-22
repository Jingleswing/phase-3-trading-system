# trading_bot/utils/logging.py
import logging
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any

def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> None:
    """
    Configure the logging system
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        log_format: Custom log format (optional)
        config: Configuration dictionary (optional)
    """
    # Get logging configuration from config if provided
    if config:
        level = config.get('system.log_level', level)
        log_file = config.get('system.log_file', log_file)
        log_format = config.get('system.log_format', log_format)
    
    # Set numeric level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Default format if not specified
    if not log_format:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure root logger
    handlers = []
    
    # Always add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)
    
    # Add file handler if log file specified
    if log_file:
        # Ensure directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        handlers=handlers
    )
    
    # Create a logger for this module
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized at level {level}")

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name
    
    Args:
        name: Logger name (typically __name__ from the calling module)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

class LoggerMixin:
    """
    Mixin class to add logging capability to any class
    
    Usage:
        class MyClass(LoggerMixin):
            def __init__(self):
                self.logger.info("Initialized")
    """
    @property
    def logger(self):
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(self.__class__.__module__ + '.' + self.__class__.__name__)
        return self._logger