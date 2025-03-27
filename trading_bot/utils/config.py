# trading_bot/utils/config.py
import os
import yaml
from typing import Dict, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)

class Config:
    """
    Configuration manager that loads settings from YAML files with support
    for nested access, and environment variable overrides.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize configuration manager
        
        Args:
            config_path: Path to main configuration file
        """
        self.config: Dict[str, Any] = {}
        
        # Load main configuration
        if not os.path.exists(config_path):
            raise ValueError(f"Configuration file does not exist: {config_path}")
            
        self._load_config(config_path)
        logger.info(f"Loaded configuration from {config_path}")
        
        # Validate that the configuration is a dictionary
        if not isinstance(self.config, dict):
            raise ValueError(f"Invalid configuration format: expected a dictionary, got {type(self.config)}")
    
    def _load_config(self, config_path: str) -> None:
        """
        Load configuration from a YAML file
        
        Args:
            config_path: Path to configuration file
        """
        try:
            with open(config_path, 'r') as f:
                loaded_config = yaml.safe_load(f)
                self.config = loaded_config
                        
        except Exception as e:
            logger.error(f"Error loading configuration from {config_path}: {e}")
            raise
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation
        
        Args:
            key_path: Path to configuration value (e.g., 'exchange.api_key')
            default: Default value if key doesn't exist
            
        Returns:
            Configuration value or default
            
        Raises:
            ValueError: If key doesn't exist and no default is provided
        """
        # Handle empty key path
        if not key_path:
            raise ValueError("Empty key path provided")
            
        # Split path by dots
        keys = key_path.split('.')
        value = self.config
        
        # Navigate through the nested dictionaries
        for i, key in enumerate(keys):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                # If default is None, raise error for missing key
                if default is None:
                    # Build the full path that was accessed for better error message
                    accessed_path = '.'.join(keys[:i+1])
                    raise ValueError(f"Required configuration key not found: '{accessed_path}'")
                return default
                
        return value
    
    def get_strict(self, key_path: str) -> Any:
        """
        Get a configuration value using dot notation with strict validation.
        No default value is allowed - if the key doesn't exist, an error is raised.
        
        Args:
            key_path: Path to configuration value (e.g., 'exchange.api_key')
            
        Returns:
            Configuration value
            
        Raises:
            ValueError: If key doesn't exist
        """
        return self.get(key_path, default=None)  # Pass None to ensure error if key missing
    
    def has_key(self, key_path: str) -> bool:
        """
        Check if a configuration key exists
        
        Args:
            key_path: Path to configuration value (e.g., 'exchange.api_key')
            
        Returns:
            True if the key exists, False otherwise
        """
        # Handle empty key path
        if not key_path:
            return False
            
        # Split path by dots
        keys = key_path.split('.')
        value = self.config
        
        # Navigate through the nested dictionaries
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return False
                
        return True
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set a configuration value using dot notation
        
        Args:
            key_path: Path to configuration value (e.g., 'exchange.api_key')
            value: Value to set
        """
        # Handle empty key path
        if not key_path:
            return
            
        # Split path by dots
        keys = key_path.split('.')
        
        # Navigate to the right location
        current = self.config
        for i, key in enumerate(keys[:-1]):
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
            
        # Set the value
        current[keys[-1]] = value
        
    def save(self, config_path: str) -> None:
        """
        Save the current configuration to a YAML file
        
        Args:
            config_path: Path to save configuration
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
            
            # Write config to file
            with open(config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
                
            logger.info(f"Configuration saved to {config_path}")
            
        except Exception as e:
            logger.error(f"Error saving configuration to {config_path}: {e}")
            raise