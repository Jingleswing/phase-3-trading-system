# trading_bot/strategies/moving_average.py
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional

from trading_bot.interfaces.strategy import Strategy
from trading_bot.models.data_models import Signal
from trading_bot.analysis.indicators import calculate_indicators
from trading_bot.utils.logging import LoggerMixin

class MovingAverageCrossover(Strategy, LoggerMixin):
    """
    Moving Average Crossover strategy.
    
    Generates buy signals when the fast moving average crosses above
    the slow moving average, and sell signals for the opposite.
    """
    
    def __init__(self, short_period: int = 20, long_period: int = 50):
        """
        Initialize the strategy
        
        Args:
            short_period: Period for the short/fast moving average
            long_period: Period for the long/slow moving average
        """
        self.short_period = short_period
        self.long_period = long_period
        self.strategy_name = f"MA_Crossover_{short_period}_{long_period}"
        self.logger.info(f"Initialized {self.strategy_name} strategy")
    
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
                    'period': self.short_period,
                    'column': 'close'
                },
                'output_column': f'sma_{self.short_period}'
            },
            {
                'name': 'sma',
                'params': {
                    'period': self.long_period,
                    'column': 'close'
                },
                'output_column': f'sma_{self.long_period}'
            }
        ]
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """
        Generate trading signals based on moving average crossovers
        
        Args:
            data: DataFrame with price data and indicators
            
        Returns:
            List of Signal objects
        """
        # Make sure we have enough data
        if len(data) < self.long_period + 1:
            self.logger.warning(f"Not enough data for {self.strategy_name} strategy")
            return []
        
        # Make sure indicators are calculated
        indicators_config = self.get_required_indicators()
        required_columns = [config['output_column'] for config in indicators_config]
        
        if not all(column in data.columns for column in required_columns):
            # Calculate required indicators if not present
            data = calculate_indicators(data, indicators_config)
        
        # Get column names
        short_col = f'sma_{self.short_period}'
        long_col = f'sma_{self.long_period}'
        
        # Initialize list to store signals
        signals = []
        
        # Look for crossovers
        for i in range(1, len(data)):
            # Get current and previous rows
            current = data.iloc[i]
            previous = data.iloc[i-1]
            
            # Check for crossover (short above long)
            if (previous[short_col] <= previous[long_col] and 
                current[short_col] > current[long_col]):
                
                # Create buy signal
                signal = Signal(
                    symbol=current['symbol'] if 'symbol' in current else data['symbol'].iloc[0],
                    timestamp=current['timestamp'],
                    signal_type='buy',
                    price=current['close'],
                    strategy_name=self.strategy_name,
                    params={
                        'short_period': self.short_period,
                        'long_period': self.long_period
                    },
                    strength=1.0  # Full strength signal
                )
                
                signals.append(signal)
                self.logger.info(f"Generated BUY signal for {signal.symbol} at {signal.price}")
            
            # Check for crossunder (short below long)
            elif (previous[short_col] >= previous[long_col] and 
                  current[short_col] < current[long_col]):
                
                # Create sell signal
                signal = Signal(
                    symbol=current['symbol'] if 'symbol' in current else data['symbol'].iloc[0],
                    timestamp=current['timestamp'],
                    signal_type='sell',
                    price=current['close'],
                    strategy_name=self.strategy_name,
                    params={
                        'short_period': self.short_period,
                        'long_period': self.long_period
                    },
                    strength=1.0  # Full strength signal
                )
                
                signals.append(signal)
                self.logger.info(f"Generated SELL signal for {signal.symbol} at {signal.price}")
        
        return signals