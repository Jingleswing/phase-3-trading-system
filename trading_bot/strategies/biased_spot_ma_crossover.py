# trading_bot/strategies/biased_spot_ma_crossover.py
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional

from trading_bot.interfaces.strategy import Strategy
from trading_bot.models.data_models import Signal
from trading_bot.analysis.indicators import calculate_indicators
from trading_bot.utils.logging import LoggerMixin

class BiasedSpotMACrossover(Strategy, LoggerMixin):
    """
    Biased Moving Average Crossover strategy for spot markets.
    
    Features:
    1. Uses different MA parameters for buy vs sell signals
    2. Position sizing based on total number of trading pairs
    
    Generates buy signals when the buy-short MA crosses above the buy-long MA,
    and sell signals when the sell-short MA crosses below the sell-long MA.
    """
    
    def __init__(self,
                 buy_short_period: int,
                 buy_long_period: int,
                 sell_short_period: int,
                 sell_long_period: int):
        """
        Initialize the biased MA crossover strategy
        
        Args:
            buy_short_period: Short period for buy signals
            buy_long_period: Long period for buy signals
            sell_short_period: Short period for sell signals
            sell_long_period: Long period for sell signals
        """
        self.buy_short_period = buy_short_period
        self.buy_long_period = buy_long_period
        self.sell_short_period = sell_short_period
        self.sell_long_period = sell_long_period
        self.logger.info(
            f"Initialized biased MA crossover strategy with "
            f"buy MA ({buy_short_period}/{buy_long_period}), "
            f"sell MA ({sell_short_period}/{sell_long_period})"
        )
    
    def get_required_indicators(self) -> List[Dict[str, Any]]:
        """
        Get list of indicators required by this strategy
        
        Returns:
            List of indicator configurations
        """
        return [
            {
                'name': 'sma',
                'params': {
                    'period': self.buy_short_period,
                    'column': 'close'
                },
                'output_column': f'sma_{self.buy_short_period}'
            },
            {
                'name': 'sma',
                'params': {
                    'period': self.buy_long_period,
                    'column': 'close'
                },
                'output_column': f'sma_{self.buy_long_period}'
            },
            {
                'name': 'sma',
                'params': {
                    'period': self.sell_short_period,
                    'column': 'close'
                },
                'output_column': f'sma_{self.sell_short_period}'
            },
            {
                'name': 'sma',
                'params': {
                    'period': self.sell_long_period,
                    'column': 'close'
                },
                'output_column': f'sma_{self.sell_long_period}'
            }
        ]
    
    def get_required_data_points(self) -> int:
        """
        Get the minimum number of data points required by this strategy
        
        Returns:
            Minimum number of data points needed
        """
        # We need the maximum of all MA periods plus 1 for the current candle
        return max(self.buy_short_period, self.buy_long_period, 
                  self.sell_short_period, self.sell_long_period) + 1
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """
        Generate trading signals based on biased moving average crossovers for spot markets
        
        Uses different MA parameters for buy vs sell signals.
        
        Args:
            data: DataFrame with price data and indicators
            
        Returns:
            List of Signal objects
        """
        # Make sure we have enough data
        required_periods = max(self.buy_long_period, self.sell_long_period) + 1
        if len(data) < required_periods:
            self.logger.warning(f"Not enough data for biased MA crossover strategy")
            return []
        
        # Make sure indicators are calculated
        indicators_config = self.get_required_indicators()
        required_columns = [config['output_column'] for config in indicators_config]
        
        if not all(column in data.columns for column in required_columns):
            # Calculate required indicators if not present
            self.logger.debug(f"Calculating indicators for columns: {required_columns}")
            data = calculate_indicators(data, indicators_config)
            self.logger.debug(f"Available columns after calculation: {data.columns.tolist()}")
        
        # Get column names
        buy_short_col = f'sma_{self.buy_short_period}'
        buy_long_col = f'sma_{self.buy_long_period}'
        sell_short_col = f'sma_{self.sell_short_period}'
        sell_long_col = f'sma_{self.sell_long_period}'
        
        # Verify all required columns exist
        required_cols = [buy_short_col, buy_long_col, sell_short_col, sell_long_col]
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            self.logger.error(f"Missing required columns: {missing_cols}")
            self.logger.error(f"Available columns: {data.columns.tolist()}")
            return []
        
        # Initialize list to store signals
        signals = []
        
        # Only check the most recent candle for crossovers
        if len(data) >= 2:
            # Get the most recent and previous rows
            current = data.iloc[-1]
            previous = data.iloc[-2]
            
            # Check for BUY signal (buy_short crosses above buy_long)
            if (previous[buy_short_col] <= previous[buy_long_col] and 
                current[buy_short_col] > current[buy_long_col]):
                
                signal = Signal(
                    symbol=current['symbol'] if 'symbol' in current else data['symbol'].iloc[0],
                    timestamp=current['timestamp'],
                    signal_type='buy',
                    price=current['close'],
                    strategy_name=f"Biased_MA_Spot_{self.buy_short_period}_{self.buy_long_period}_{self.sell_short_period}_{self.sell_long_period}",
                    params={
                        'buy_short_period': self.buy_short_period,
                        'buy_long_period': self.buy_long_period,
                        'market_type': 'spot'
                    },
                    strength=1.0
                )
                
                signals.append(signal)
                self.logger.info(f"Generated BUY signal for {signal.symbol} at {signal.price} in spot market")
            
            # Check for CLOSE signal (sell_short crosses below sell_long)
            elif (previous[sell_short_col] >= previous[sell_long_col] and 
                  current[sell_short_col] < current[sell_long_col]):
                
                signal = Signal(
                    symbol=current['symbol'] if 'symbol' in current else data['symbol'].iloc[0],
                    timestamp=current['timestamp'],
                    signal_type='close',
                    price=current['close'],
                    strategy_name=f"Biased_MA_Spot_{self.buy_short_period}_{self.buy_long_period}_{self.sell_short_period}_{self.sell_long_period}",
                    params={
                        'sell_short_period': self.sell_short_period,
                        'sell_long_period': self.sell_long_period,
                        'market_type': 'spot',
                        'action': 'close_position'
                    },
                    strength=1.0
                )
                
                signals.append(signal)
                self.logger.info(f"Generated CLOSE signal for {signal.symbol} at {signal.price} in spot market")
        
        return signals 