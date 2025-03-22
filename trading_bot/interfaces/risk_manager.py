# trading_bot/interfaces/risk_manager.py
from abc import ABC, abstractmethod
from typing import Dict, Tuple, Any, Optional
from trading_bot.models.data_models import Signal, Order

class RiskManager(ABC):
    """
    Abstract interface for risk management.
    
    Risk managers evaluate signals and determine appropriate position sizes
    based on risk parameters.
    """
    
    @abstractmethod
    def validate_signal(self, signal: Signal) -> Tuple[bool, str]:
        """
        Validate if a signal should be executed based on risk rules
        
        Args:
            signal: Signal to validate
            
        Returns:
            Tuple of (is_valid, reason) where:
            - is_valid: True if signal meets risk criteria
            - reason: Explanation if not valid
        """
        pass
    
    @abstractmethod
    def calculate_position_size(self, signal: Signal) -> float:
        """
        Calculate appropriate position size for a signal
        
        Args:
            signal: Trading signal
            
        Returns:
            Position size in base currency
        """
        pass
    
    @abstractmethod
    def set_stop_loss(self, signal: Signal) -> Optional[Order]:
        """
        Create a stop loss order for a signal
        
        Args:
            signal: Trading signal
            
        Returns:
            Stop loss order or None if not applicable
        """
        pass