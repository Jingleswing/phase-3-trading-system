# trading_bot/interfaces/strategy.py
from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, List, Any, Optional
from trading_bot.models.data_models import Signal

class Strategy(ABC):
    """
    Abstract interface for trading strategies.
    
    Strategies analyze market data and generate trading signals.
    """
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """
        Analyze data and generate trading signals
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            List of Signal objects
        """
        pass
    
    @abstractmethod
    def get_required_indicators(self) -> List[Dict[str, Any]]:
        """
        Get list of indicators required by this strategy
        
        Returns:
            List of indicator configurations
            Example: [
                {'name': 'sma', 'params': {'period': 20, 'column': 'close'}},
                {'name': 'sma', 'params': {'period': 50, 'column': 'close'}}
            ]
        """
        pass
    
    @abstractmethod
    def get_required_data_points(self) -> int:
        """
        Get the minimum number of data points required by this strategy
        
        Returns:
            Minimum number of data points needed
        """
        pass