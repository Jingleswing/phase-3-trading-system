# trading_bot/utils/logging.py
import logging
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler

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

def setup_enhanced_logging(config: Optional[Dict[str, Any]] = None):
    """
    Set up enhanced logging with rotation and specialized loggers for debugging
    
    Args:
        config: Configuration dictionary
    """
    if config is None:
        config = {}
    
    # Get configuration    
    system_config = config.get('system', {})
    log_level_name = system_config.get('log_level', 'INFO')
    log_level = getattr(logging, log_level_name)
    log_dir = "logs"
    
    # Create log directory if it doesn't exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Common formatter
    standard_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler to root logger
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(standard_formatter)
    root_logger.addHandler(console_handler)
    
    # Add rotating file handler to root logger
    root_handler = RotatingFileHandler(
        f"{log_dir}/trading_bot.log", 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    root_handler.setFormatter(standard_formatter)
    root_logger.addHandler(root_handler)
    
    # Create specialized loggers
    loggers = {
        "indicators": logging.DEBUG,
        "signal_diagnostics": logging.DEBUG,
        "ma_values": logging.DEBUG,
        "crossovers": logging.DEBUG,
        "positions": logging.DEBUG,
        "orders": logging.DEBUG,
        "data": logging.DEBUG
    }
    
    for logger_name, level in loggers.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        
        # Clear existing handlers to avoid duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            
        # Create appropriate handler based on logger type
        if logger_name == "ma_values":
            # CSV format for values that will be stored for analysis
            handler = RotatingFileHandler(
                f"{log_dir}/{logger_name}.csv",
                maxBytes=5*1024*1024,  # 5MB
                backupCount=3
            )
            # No formatter for CSV data
        else:
            handler = RotatingFileHandler(
                f"{log_dir}/{logger_name}.log",
                maxBytes=5*1024*1024,  # 5MB
                backupCount=3
            )
            handler.setFormatter(standard_formatter)
            
        logger.addHandler(handler)
        logger.propagate = False  # Don't propagate to root
    
    # Write CSV header for MA values
    ma_logger = logging.getLogger("ma_values")
    ma_logger.debug("timestamp,symbol,price,buy_short_ma,buy_long_ma,sell_short_ma,sell_long_ma")
    
    logging.info(f"Enhanced logging setup complete. Log files will be stored in {os.path.abspath(log_dir)}")