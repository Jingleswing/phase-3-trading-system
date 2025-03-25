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
    if config and 'system' in config:
        system_config = config['system']
        level = system_config.get('log_level', level)
        log_file = system_config.get('log_file', log_file)
        log_format = system_config.get('log_format', log_format)
    
    # Set numeric level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Default format if not specified
    if not log_format:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure handlers
    handlers = []
    
    # Always add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)
    
    # Add file handler if log file specified
    if log_file:
        # Use absolute path if log_file is a relative path
        if not os.path.isabs(log_file):
            # Get the absolute path to the project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            log_file = os.path.join(project_root, log_file)
            
        # Ensure directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Create file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    
    # Configure root logger - reset first to ensure our config takes effect
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    
    # Add our handlers and set level
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(numeric_level)
    
    # Log setup information
    logging.getLogger(__name__).info(f"Logging initialized at level {level}")
    if log_file:
        logging.getLogger(__name__).info(f"Logging to file: {log_file}")

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