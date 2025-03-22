# trading_bot/utils/config.py
import os
import yaml
from typing import Dict, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)

class Config:
    """
    Configuration manager that loads settings from YAML files with support
    for default values, nested access, and environment variable overrides.
    """
    
    def __init__(self, config_path: Optional[str] = None, default_config_path: Optional[str] = None):
        """
        Initialize configuration manager
        
        Args:
            config_path: Path to main configuration file (optional)
            default_config_path: Path to default configuration file (optional)
        """
        self.config: Dict[str, Any] = {}
        
        # Load default configuration if provided
        if default_config_path and os.path.exists(default_config_path):
            self._load_config(default_config_path)
            logger.info(f"Loaded default configuration from {default_config_path}")
        
        # Load main configuration if provided (overrides defaults)
        if config_path and os.path.exists(config_path):
            self._load_config(config_path, override=True)
            logger.info(f"Loaded configuration from {config_path}")
    
    def _load_config(self, config_path: str, override: bool = False) -> None:
        """
        Load configuration from a YAML file
        
        Args:
            config_path: Path to configuration file
            override: Whether to override existing values
        """
        try:
            with open(config_path, 'r') as f:
                loaded_config = yaml.safe_load(f)
                
                if override:
                    # Update existing config with new values
                    self._update_dict(self.config, loaded_config)
                else:
                    # Set config if empty, otherwise update
                    if not self.config:
                        self.config = loaded_config
                    else:
                        self._update_dict(self.config, loaded_config)
                        
        except Exception as e:
            logger.error(f"Error loading configuration from {config_path}: {e}")
            raise
    
    def _update_dict(self, target: Dict, source: Dict) -> None:
        """
        Recursively update a dictionary with values from another dictionary
        
        Args:
            target: Dictionary to update
            source: Dictionary with new values
        """
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                # Recursively update nested dictionaries
                self._update_dict(target[key], value)
            else:
                # Update or add value
                target[key] = value
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation
        
        Args:
            key_path: Path to configuration value (e.g., 'exchange.api_key')
            default: Default value if key doesn't exist
            
        Returns:
            Configuration value or default
        """
        # Handle empty key path
        if not key_path:
            return default
            
        # Split path by dots
        keys = key_path.split('.')
        value = self.config
        
        # Navigate through the nested dictionaries
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
                
        return value
    
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