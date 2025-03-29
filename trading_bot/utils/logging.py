# trading_bot/utils/logging.py
import logging
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name
    
    Args:
        name: Logger name (typically __name__ from the calling module)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

def setup_logging(config: Optional[Dict[str, Any]] = None, level: str = "INFO"):
    """
    Set up logging with console output and a single rotating file.
    Relies on logger namespacing for filtering.
    
    Args:
        config: Configuration dictionary (used for log level if provided)
        level: Logging level string (e.g., "DEBUG", "INFO") - overrides config if provided.
    """
    if config is None:
        config = {}
    
    # Determine log level: Command line arg > config file > default
    system_config = config.get('system', {})
    log_level_name = level or system_config.get('log_level', 'INFO')
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)
    
    # Define log directory and main log file path
    log_dir = "logs"
    log_file = os.path.join(log_dir, "trading_bot.log")
    
    # Create log directory if it doesn't exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Standard formatter
    standard_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get root logger
    root_logger = logging.getLogger()
    
    # Clear existing handlers to avoid duplicates from previous runs/imports
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close() # Close handlers before removing
    
    # Set root logger level - this determines the minimum severity processed
    root_logger.setLevel(log_level)
    
    # Create and add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(standard_formatter)
    # Handler level determines what this specific handler outputs
    console_handler.setLevel(log_level) 
    root_logger.addHandler(console_handler)
    
    # Create and add rotating file handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8' # Explicitly set encoding
    )
    file_handler.setFormatter(standard_formatter)
    # Handler level determines what this specific handler outputs
    file_handler.setLevel(log_level) 
    root_logger.addHandler(file_handler)
    
    # Removed specialized loggers and handlers
    # Removed logger.propagate = False settings
    # Removed ma_values.csv setup

    # Log confirmation
    logging.info(f"Logging setup complete. Level: {log_level_name}. Outputting to console and {os.path.abspath(log_file)}")