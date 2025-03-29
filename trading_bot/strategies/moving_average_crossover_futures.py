# trading_bot/strategies/moving_average_crossover_futures.py
import pandas as pd
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from trading_bot.interfaces.strategy import Strategy
from trading_bot.models.data_models import Signal
from trading_bot.analysis.indicators import calculate_indicators

class MovingAverageCrossoverFutures(Strategy):
    """
    Moving Average Crossover strategy for futures markets.
    
    Generates buy signals when the fast moving average crosses above
    the slow moving average, and sell signals for the opposite.
    
    Optimized for futures markets where both long and short positions are common.
    """
    
    def __init__(self, 
                short_period: int, 
                long_period: int,
                leverage: int):
        """
        Initialize the strategy
        
        Args:
            short_period: Period for the short/fast moving average
            long_period: Period for the long/slow moving average
            leverage: Leverage level to use for futures trading
        """
        self.short_period = short_period
        self.long_period = long_period
        self.leverage = leverage
        self.logger = logging.getLogger(__name__)
        self.strategy_name = f"MA_Crossover_Futures_{short_period}_{long_period}"
        self.market_type = "futures"
        self.logger.info(
            f"Initialized {self.strategy_name} strategy for {self.market_type} market "
            f"with leverage={leverage}x"
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
    
    def get_required_data_points(self) -> int:
        """
        Get the minimum number of data points required by this strategy
        
        Returns:
            Minimum number of data points needed
        """
        # We need the maximum of both MA periods plus 1 for the current candle
        return max(self.short_period, self.long_period) + 1
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """
        Generate trading signals based on moving average crossovers for futures markets
        
        Only generates signals for the most recent candle to avoid duplicate signals.
        
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
        
        # Only check the most recent candle for crossovers
        if len(data) >= 2:
            # Get the most recent and previous rows
            current = data.iloc[-1]
            previous = data.iloc[-2]
            
            # Log current SMA values and their relationship
            current_short = current[short_col]
            current_long = current[long_col]
            current_price = current['close']
            short_long_diff = current_short - current_long
            short_long_diff_pct = (short_long_diff / current_long) * 100
            
            self.logger.info(
                f"Current SMAs for {current['symbol']}: "
                f"Short({self.short_period})={current_short:.2f}, "
                f"Long({self.long_period})={current_long:.2f}, "
                f"Price={current_price:.2f}, "
                f"Diff={short_long_diff:.2f} ({short_long_diff_pct:.2f}%)"
            )
            
            # Check for crossover (short above long)
            if (previous[short_col] <= previous[long_col] and 
                current[short_col] > current[long_col]):
                
                # Create buy signal for futures market
                signal = Signal(
                    symbol=current['symbol'] if 'symbol' in current else data['symbol'].iloc[0],
                    timestamp=current['timestamp'],
                    signal_type='buy',
                    price=current['close'],
                    strategy_name=self.strategy_name,
                    params={
                        'short_period': self.short_period,
                        'long_period': self.long_period,
                        'market_type': self.market_type,
                        'leverage': self.leverage
                    },
                    strength=1.0  # Full strength signal
                )
                
                signals.append(signal)
                self.logger.info(
                    f"Generated BUY signal for {signal.symbol} at {signal.price} in {self.market_type} market "
                    f"(leverage: {self.leverage}x)"
                )
            
            # Check for crossunder (short below long)
            elif (previous[short_col] >= previous[long_col] and 
                  current[short_col] < current[long_col]):
                
                # Create sell signal for futures market
                signal = Signal(
                    symbol=current['symbol'] if 'symbol' in current else data['symbol'].iloc[0],
                    timestamp=current['timestamp'],
                    signal_type='sell',
                    price=current['close'],
                    strategy_name=self.strategy_name,
                    params={
                        'short_period': self.short_period,
                        'long_period': self.long_period,
                        'market_type': self.market_type,
                        'leverage': self.leverage
                    },
                    strength=1.0  # Full strength signal
                )
                
                signals.append(signal)
                self.logger.info(
                    f"Generated SELL signal for {signal.symbol} at {signal.price} in {self.market_type} market "
                    f"(leverage: {self.leverage}x)"
                )
        
        return signals