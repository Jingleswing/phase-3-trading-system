# trading_bot/strategies/biased_spot_ma_crossover.py
import pandas as pd
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional
import os

from trading_bot.interfaces.strategy import Strategy
from trading_bot.models.data_models import Signal, PositionTracker
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
                 sell_long_period: int,
                 exchange=None):
        """
        Initialize the biased MA crossover strategy
        
        Args:
            buy_short_period: Short period for buy signals
            buy_long_period: Long period for buy signals
            sell_short_period: Short period for sell signals
            sell_long_period: Long period for sell signals
            exchange: Optional exchange object for checking positions
        """
        self.buy_short_period = buy_short_period
        self.buy_long_period = buy_long_period
        self.sell_short_period = sell_short_period
        self.sell_long_period = sell_long_period
        self.exchange = exchange
        self.position_tracker = None
        self.debug_logger = self._setup_debug_logger()
        
        # Initialize position tracker if exchange is provided
        if self.exchange:
            self.position_tracker = PositionTracker(self.exchange)
            
        self.logger.info(
            f"Initialized biased MA crossover strategy with "
            f"buy MA ({buy_short_period}/{buy_long_period}), "
            f"sell MA ({sell_short_period}/{sell_long_period})"
        )
    
    def _setup_debug_logger(self):
        """Set up a dedicated logger for signal diagnostics"""
        logger = logging.getLogger("signal_diagnostics")
        
        # Create logs directory if it doesn't exist
        if not os.path.exists("logs"):
            os.makedirs("logs")
            
        # Check if handler already exists to avoid duplicate handlers
        if not logger.handlers:
            # Create file handler for signal diagnostics
            fh = logging.FileHandler("logs/signal_diagnostics.log")
            fh.setLevel(logging.DEBUG)
            
            # Create formatter for detailed diagnostics
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - '
                '%(message)s [%(filename)s:%(lineno)d]'
            )
            fh.setFormatter(formatter)
            
            # Add the handler to logger
            logger.addHandler(fh)
            logger.setLevel(logging.DEBUG)
            logger.propagate = False  # Don't propagate to root logger
        
        return logger
    
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
    
    def log_signal_diagnostics(self, symbol, data_dict, condition_name, condition_result):
        """
        Log detailed information about signal conditions for diagnostic purposes
        
        Args:
            symbol: Trading symbol
            data_dict: Dictionary of values to log
            condition_name: Name of the condition being evaluated
            condition_result: Result of the condition (True/False)
        """
        message = (f"SIGNAL DIAGNOSTIC: {symbol} - {condition_name}: {condition_result}\n"
                  f"  Current Price: {data_dict.get('price', 'N/A')}\n"
                  f"  Buy MAs: Short({self.buy_short_period})={data_dict.get('buy_short_ma', 'N/A'):.6f}, "
                  f"Long({self.buy_long_period})={data_dict.get('buy_long_ma', 'N/A'):.6f}\n"
                  f"  Sell MAs: Short({self.sell_short_period})={data_dict.get('sell_short_ma', 'N/A'):.6f}, "
                  f"Long({self.sell_long_period})={data_dict.get('sell_long_ma', 'N/A'):.6f}\n"
                  f"  Buy Crossover: {data_dict.get('buy_crossover', 'N/A')}\n"
                  f"  Sell Crossover: {data_dict.get('sell_crossover', 'N/A')}\n"
                  f"  In Sell Configuration: {data_dict.get('is_sell_configuration', 'N/A')}\n"
                  f"  Has Position: {data_dict.get('has_position', 'N/A')}\n"
                  f"  Position Amount: {data_dict.get('position_amount', 'N/A')}")
        
        self.debug_logger.info(message)
        
        # Also log to crossovers logger if this is a crossover condition
        if "CROSSOVER" in condition_name or "CONFIGURATION" in condition_name:
            crossover_logger = logging.getLogger("crossovers")
            crossover_logger.debug(message)
    
    def check_positions(self, symbol):
        """
        Check if we have an open position for the given symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Tuple of (has_position, position_amount)
        """
        has_position = False
        position_amount = 0
        
        if self.position_tracker:
            try:
                # Get position without forcing an update
                position = self.position_tracker.get_position(symbol)
                
                positions_logger = logging.getLogger("positions")
                
                if position:
                    # Calculate position value in USD
                    position_value = position.amount * position.current_price
                    
                    # Only consider it a valid position if value > $1
                    has_position = position.amount > 0 and position_value > 1.0
                    position_amount = position.amount
                    
                    # Log detailed position information
                    positions_logger.debug(
                        f"Position details for {symbol}:\n"
                        f"  Amount: {position.amount:.8f}\n"
                        f"  Entry price: {position.entry_price:.6f}\n"
                        f"  Current price: {position.current_price:.6f}\n"
                        f"  Position value: ${position_value:.2f}\n"
                        f"  Side: {position.side}\n"
                        f"  Unrealized PnL: {position.unrealized_pnl:.8f}\n"
                        f"  Entry time: {position.entry_time}\n"
                        f"  Valid position (value > $1): {has_position}"
                    )
                else:
                    positions_logger.debug(f"No position found for {symbol}")
                    
            except Exception as e:
                positions_logger.error(f"Error checking position for {symbol}: {e}")
                
        return has_position, position_amount
    
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
            self.logger.warning(f"Not enough data for biased MA crossover strategy: {len(data)}/{required_periods}")
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
            
            # Get the current symbol
            symbol = current['symbol'] if 'symbol' in current else data['symbol'].iloc[0]
            current_price = current['close']
            
            # Log all MA values at the beginning of processing
            self.debug_logger.info(
                f"Processing {symbol} - Current price: {current_price}\n"
                f"  Previous MAs: Buy Short={previous[buy_short_col]:.6f}, Buy Long={previous[buy_long_col]:.6f}, "
                f"Sell Short={previous[sell_short_col]:.6f}, Sell Long={previous[sell_long_col]:.6f}\n"
                f"  Current MAs: Buy Short={current[buy_short_col]:.6f}, Buy Long={current[buy_long_col]:.6f}, "
                f"Sell Short={current[sell_short_col]:.6f}, Sell Long={current[sell_long_col]:.6f}"
            )
            
            # Also log to MA values CSV for data analysis
            ma_logger = logging.getLogger("ma_values")
            ma_logger.debug(
                f"{current['timestamp']},{symbol},{current_price:.6f},"
                f"{current[buy_short_col]:.6f},{current[buy_long_col]:.6f},"
                f"{current[sell_short_col]:.6f},{current[sell_long_col]:.6f}"
            )
            
            # Get current MA values
            current_buy_short_ma = current[buy_short_col]
            current_buy_long_ma = current[buy_long_col]
            current_sell_short_ma = current[sell_short_col]
            current_sell_long_ma = current[sell_long_col]
            
            # Check conditions
            is_sell_configuration = current_sell_short_ma < current_sell_long_ma
            buy_crossover = (previous[buy_short_col] <= previous[buy_long_col] and 
                            current_buy_short_ma > current_buy_long_ma)
            sell_crossover = (previous[sell_short_col] >= previous[sell_long_col] and 
                             current_sell_short_ma < current_sell_long_ma)
            
            # Log detailed crossover check information
            crossover_logger = logging.getLogger("crossovers")
            crossover_logger.debug(
                f"CROSSOVER CHECK: {symbol} @ {current['timestamp']}\n"
                f"Previous buy: short({previous[buy_short_col]:.6f}) {'>' if previous[buy_short_col] > previous[buy_long_col] else '<='} long({previous[buy_long_col]:.6f})\n"
                f"Current buy: short({current_buy_short_ma:.6f}) {'>' if current_buy_short_ma > current_buy_long_ma else '<='} long({current_buy_long_ma:.6f})\n"
                f"BUY CROSSOVER DETECTED: {buy_crossover}\n\n"
                f"Previous sell: short({previous[sell_short_col]:.6f}) {'>' if previous[sell_short_col] > previous[sell_long_col] else '<='} long({previous[sell_long_col]:.6f})\n"
                f"Current sell: short({current_sell_short_ma:.6f}) {'>' if current_sell_short_ma > current_sell_long_ma else '<='} long({current_sell_long_ma:.6f})\n"
                f"SELL CROSSOVER DETECTED: {sell_crossover}"
            )
            
            # Check for positions
            has_position, position_amount = self.check_positions(symbol)
            
            # Prepare diagnostic data
            diagnostic_data = {
                'price': current_price,
                'buy_short_ma': current_buy_short_ma,
                'buy_long_ma': current_buy_long_ma,
                'sell_short_ma': current_sell_short_ma,
                'sell_long_ma': current_sell_long_ma,
                'buy_crossover': buy_crossover,
                'sell_crossover': sell_crossover,
                'is_sell_configuration': is_sell_configuration,
                'has_position': has_position,
                'position_amount': position_amount
            }
            
            # Log buy condition
            self.log_signal_diagnostics(
                symbol, diagnostic_data, "BUY_CONDITION", buy_crossover
            )
            
            # Check for BUY signal (buy_short crosses above buy_long)
            # Only generate buy signals if we don't already have a position
            if buy_crossover and not has_position:
                signal = Signal(
                    symbol=symbol,
                    timestamp=current['timestamp'],
                    signal_type='buy',
                    price=current_price,
                    strategy_name=f"Biased_MA_Spot_{self.buy_short_period}_{self.buy_long_period}_{self.sell_short_period}_{self.sell_long_period}",
                    params={
                        'buy_short_period': self.buy_short_period,
                        'buy_long_period': self.buy_long_period,
                        'sell_short_period': self.sell_short_period,
                        'sell_long_period': self.sell_long_period,
                        'buy_short_ma_value': current_buy_short_ma,
                        'buy_long_ma_value': current_buy_long_ma,
                        'sell_short_ma_value': current_sell_short_ma,
                        'sell_long_ma_value': current_sell_long_ma,
                        'market_type': 'spot'
                    },
                    strength=1.0
                )
                
                signals.append(signal)
                self.logger.info(f"Generated BUY signal for {signal.symbol} at {signal.price} in spot market")
            elif buy_crossover and has_position:
                self.logger.info(f"Buy crossover detected for {symbol} but position already exists, not generating signal")
            
            # Log sell conditions
            self.log_signal_diagnostics(
                symbol, diagnostic_data, "SELL_CROSSOVER", sell_crossover
            )
            self.log_signal_diagnostics(
                symbol, diagnostic_data, "SELL_CONFIGURATION_WITH_POSITION", 
                is_sell_configuration and has_position
            )
            
            # Generate close signal if:
            # 1. We have a sell crossover only
            should_generate_close = sell_crossover
            
            # Log the final close signal decision
            self.log_signal_diagnostics(
                symbol, diagnostic_data, "SHOULD_CLOSE", should_generate_close
            )
            
            # Only generate close signals if we have a position or there's a crossover
            if should_generate_close and (has_position or sell_crossover):
                signal = Signal(
                    symbol=symbol,
                    timestamp=current['timestamp'],
                    signal_type='close',
                    price=current_price,
                    strategy_name=f"Biased_MA_Spot_{self.buy_short_period}_{self.buy_long_period}_{self.sell_short_period}_{self.sell_long_period}",
                    params={
                        'sell_short_period': self.sell_short_period,
                        'sell_long_period': self.sell_long_period,
                        'sell_short_ma_value': current_sell_short_ma,
                        'sell_long_ma_value': current_sell_long_ma, 
                        'buy_short_ma_value': current_buy_short_ma,
                        'buy_long_ma_value': current_buy_long_ma,
                        'market_type': 'spot',
                        'action': 'close_position',
                        'reason': 'sell_crossover',
                        'has_position': has_position,
                        'position_amount': position_amount
                    },
                    strength=1.0
                )
                
                signals.append(signal)
                reason = "CROSSOVER"
                self.logger.info(
                    f"Generated CLOSE signal for {signal.symbol} at {signal.price} "
                    f"in spot market (reason: {reason}, has_position: {has_position})"
                )
        
        return signals 