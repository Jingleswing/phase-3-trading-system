# trading_bot/interfaces/data_provider.py
from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

class DataProvider(ABC):
    """
    Abstract interface for market data providers.
    
    This interface defines methods for retrieving market data from various sources
    such as exchanges, CSV files, or APIs.
    """
    
    @abstractmethod
    def get_historical_data(self, 
                           symbol: str, 
                           timeframe: str, 
                           since: Optional[Union[datetime, int]] = None,
                           limit: Optional[int] = None) -> pd.DataFrame:
        """
        Retrieve historical OHLCV data
        
        Args:
            symbol: Trading pair symbol (e.g. 'ETH/USDT')
            timeframe: Data timeframe (e.g. '1m', '5m', '1h')
            since: Starting time for data retrieval
            limit: Maximum number of candles to retrieve
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        pass
    
    @abstractmethod
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get current ticker data for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Dictionary with ticker data including at minimum:
            {'bid': float, 'ask': float, 'last': float}
        """
        pass
    
    @abstractmethod
    def get_balance(self) -> Dict[str, Dict[str, float]]:
        """
        Get account balances
        
        Returns:
            Dictionary of currencies and their balances:
            {
                'ETH': {'free': 1.0, 'used': 0.0, 'total': 1.0},
                'USDT': {'free': 1000.0, 'used': 0.0, 'total': 1000.0}
            }
        """
        pass