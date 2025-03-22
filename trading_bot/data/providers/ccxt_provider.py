# trading_bot/data/providers/ccxt_provider.py
import ccxt
import pandas as pd
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from trading_bot.interfaces.data_provider import DataProvider
from trading_bot.utils.logging import LoggerMixin

class CCXTProvider(DataProvider, LoggerMixin):
    """
    Data provider using the CCXT library to connect to cryptocurrency exchanges.
    
    This implementation works with any exchange supported by CCXT, including Bybit.
    """
    
    def __init__(self, 
                exchange_id: str, 
                api_key: Optional[str] = None, 
                secret: Optional[str] = None, 
                params: Optional[Dict[str, Any]] = None):
        """
        Initialize the CCXT exchange connection
        
        Args:
            exchange_id: CCXT exchange ID (e.g. 'bybit', 'binance')
            api_key: API key for authenticated requests
            secret: API secret for authenticated requests
            params: Additional parameters for the exchange
        """
        self.exchange_id = exchange_id
        
        # Initialize exchange parameters
        exchange_params = {
            'enableRateLimit': True,  # Respect exchange rate limits
        }
        
        # Add API credentials if provided
        if api_key and secret:
            exchange_params.update({
                'apiKey': api_key,
                'secret': secret,
            })
        
        # Add any additional parameters
        if params:
            exchange_params.update(params)
        
        # Create the exchange instance
        try:
            exchange_class = getattr(ccxt, exchange_id)
            self.exchange = exchange_class(exchange_params)
            self.logger.info(f"Initialized connection to {exchange_id}")
            
            # Load markets to get trading pairs info
            self.exchange.load_markets()
            self.logger.info(f"Loaded markets for {exchange_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize {exchange_id}: {e}")
            raise
    
    def get_historical_data(self, 
                           symbol: str, 
                           timeframe: str = '1m', 
                           since: Optional[Union[datetime, int]] = None,
                           limit: Optional[int] = None) -> pd.DataFrame:
        """
        Retrieve historical OHLCV data from the exchange
        
        Args:
            symbol: Trading pair symbol (e.g. 'ETH/USDT')
            timeframe: Data timeframe (e.g. '1m', '5m', '1h')
            since: Starting time for data retrieval
            limit: Maximum number of candles to retrieve
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        try:
            # Convert datetime to timestamp in milliseconds if provided
            if since is not None and isinstance(since, datetime):
                since = int(since.timestamp() * 1000)
            
            # Set default limit if not provided
            if limit is None:
                limit = 100  # Default to 100 candles
            
            # Fetch OHLCV data
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=limit
            )
            
            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv, 
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Add symbol column
            df['symbol'] = symbol
            
            self.logger.debug(f"Retrieved {len(df)} candles for {symbol} ({timeframe})")
            return df
            
        except Exception as e:
            self.logger.error(f"Error retrieving historical data for {symbol}: {e}")
            raise
    
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get current ticker data for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Dictionary with ticker data
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            self.logger.debug(f"Retrieved ticker for {symbol}: {ticker['last']}")
            return ticker
        except Exception as e:
            self.logger.error(f"Error retrieving ticker for {symbol}: {e}")
            raise
    
    def get_balance(self) -> Dict[str, Dict[str, float]]:
        """
        Get account balances
        
        Returns:
            Dictionary of currencies and their balances
        """
        try:
            balance = self.exchange.fetch_balance()
            # Remove metadata and keep only currency balances
            currencies = {k: v for k, v in balance.items() if isinstance(v, dict) and 'free' in v}
            
            self.logger.debug(f"Retrieved balances for {len(currencies)} currencies")
            return currencies
        except Exception as e:
            self.logger.error(f"Error retrieving balances: {e}")
            raise
    
    def get_order_book(self, symbol: str, limit: Optional[int] = None) -> Dict[str, List]:
        """
        Get the order book for a symbol
        
        Args:
            symbol: Trading pair symbol
            limit: Depth of the order book
            
        Returns:
            Dictionary with 'bids' and 'asks'
        """
        try:
            params = {}
            if limit:
                params['limit'] = limit
                
            order_book = self.exchange.fetch_order_book(symbol, params=params)
            self.logger.debug(f"Retrieved order book for {symbol} with {len(order_book['bids'])} bids and {len(order_book['asks'])} asks")
            return order_book
        except Exception as e:
            self.logger.error(f"Error retrieving order book for {symbol}: {e}")
            raise
    
    def get_exchange_info(self) -> Dict[str, Any]:
        """
        Get exchange information and trading rules
        
        Returns:
            Dictionary with exchange information
        """
        return {
            'id': self.exchange.id,
            'name': self.exchange.name,
            'symbols': list(self.exchange.markets.keys()),
            'timeframes': list(self.exchange.timeframes.keys()) if hasattr(self.exchange, 'timeframes') else [],
            'has': self.exchange.has,
        }