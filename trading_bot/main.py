# trading_bot/main.py
import time
import argparse
import os
import signal
import sys
import logging
from typing import Dict, Any, List
from dotenv import load_dotenv

from trading_bot.utils.config import Config
from trading_bot.utils.logging import setup_logging, setup_enhanced_logging
from trading_bot.utils.events import EventBus, EventType, Event

from trading_bot.data.providers.ccxt_provider import CCXTProvider
from trading_bot.strategies.factory import StrategyFactory
from trading_bot.execution.ccxt_executor import CCXTExecutor
from trading_bot.risk.basic_risk_manager import BasicRiskManager
from trading_bot.models.data_models import Order, Signal

class TradingBot:
    """
    Main trading bot class that orchestrates all components
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize the trading bot
        
        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        if not config_path or not os.path.exists(config_path):
            raise ValueError(f"Config file is required and must exist: {config_path}")
            
        self.config = Config(config_path)
        
        # Set up logging with config - use enhanced logging for better debugging
        setup_enhanced_logging(config=self.config.config)
        self.logger = logging.getLogger(__name__)
        
        # Create event bus
        self.event_bus = EventBus()
        
        # Set up components
        self._setup_components()
        
        # Register event handlers
        self._register_events()
        
        # Flag to control the main loop
        self.running = False
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
        # Track drawdown positions that failed to close
        self._drawdown_close_retries = {}
        
        self.logger.info("Trading bot initialized")
    
    def _setup_components(self):
        """Set up all bot components based on configuration"""
        load_dotenv()

        # Set up data provider with required parameters
        if not self.config.has_key('exchange'):
            raise ValueError("Configuration missing required section: 'exchange'")
            
        # Required exchange parameters
        exchange_id = self.config.get_strict('exchange.id')
        api_key = os.environ.get('EXCHANGE_API_KEY')
        secret = os.environ.get('EXCHANGE_SECRET')
        
        # Validate that keys were found
        if not api_key:
            raise ValueError("API key not found. Please set EXCHANGE_API_KEY environment variable.")
        if not secret:
            raise ValueError("API secret not found. Please set EXCHANGE_SECRET environment variable.")
        
        # Optional exchange parameters (may have defaults)
        params = self.config.get('exchange.params', {})
        
        self.data_provider = CCXTProvider(
            exchange_id=exchange_id,
            api_key=api_key,
            secret=secret,
            params=params
        )
        
        # Create strategies for different market types
        self.strategies = {}
        
        # Required trading parameters
        if not self.config.has_key('trading'):
            raise ValueError("Configuration missing required section: 'trading'")
            
        if not self.config.has_key('trading.symbols'):
            raise ValueError("Trading configuration missing required parameter: 'symbols'")
            
        trading_symbols = self.config.get_strict('trading.symbols')
        
        if not trading_symbols:
            raise ValueError("No trading symbols configured. At least one symbol is required.")
            
        # Required trading timeframe - must be in config
        timeframe = self.config.get_strict('trading.timeframe')
        
        # Required strategy configuration
        if not self.config.has_key('strategy'):
            raise ValueError("Configuration missing required section: 'strategy'")
            
        # Count total trading pairs for position sizing
        total_trading_pairs = len(trading_symbols)
        self.logger.info(f"Total trading pairs: {total_trading_pairs}")
        
        for symbol_config in trading_symbols:
            if isinstance(symbol_config, dict):
                if 'symbol' not in symbol_config:
                    raise ValueError(f"Symbol configuration missing required parameter: 'symbol'")
                    
                symbol = symbol_config['symbol']
                
                if 'market_type' not in symbol_config:
                    raise ValueError(f"Symbol configuration for {symbol} missing required parameter: 'market_type'")
                    
                market_type = symbol_config['market_type']
                
                # Get strategy configuration from config file
                strategy_config = self.config.config['strategy'].copy()
                
                # Add timeframe to strategy config
                strategy_config['timeframe'] = timeframe
                
                # Create the strategy
                self.strategies[symbol] = StrategyFactory.create_strategy(
                    strategy_config,
                    exchange=self.data_provider.exchange
                )
                self.logger.info(f"Created {market_type} strategy for {symbol}")
            else:
                # If symbol is just a string, assume it's a spot market
                symbol = symbol_config
                
                strategy_config = self.config.config['strategy'].copy()
                
                # Add timeframe to strategy config
                strategy_config['timeframe'] = timeframe
                
                self.strategies[symbol] = StrategyFactory.create_strategy(
                    strategy_config,
                    exchange=self.data_provider.exchange
                )
                self.logger.info(f"Created spot strategy for {symbol}")
        
        # Log the configured timeframe
        self.logger.info(f"Trading {list(self.strategies.keys())} on {timeframe} timeframe")
        
        # Check if any valid strategies were created
        if not self.strategies:
            raise ValueError("No valid trading strategies configured")
        
        # Required trading parameter (must be in config)
        trading_enabled = self.config.get_strict('trading.enabled')
        dry_run = not trading_enabled
        
        self.executor = CCXTExecutor(
            exchange=self.data_provider.exchange,
            dry_run=dry_run
        )
        
        # Required risk configuration
        if not self.config.has_key('risk'):
            raise ValueError("Configuration missing required section: 'risk'")
            
        # Required risk parameters (must be in config)
        max_drawdown = self.config.get_strict('risk.max_drawdown')
        
        self.risk_manager = BasicRiskManager(
            exchange=self.data_provider.exchange,
            max_open_trades=total_trading_pairs,
            max_drawdown=max_drawdown
        )
        
        # Log risk manager configuration
        self.logger.info(f"Risk manager configured with max drawdown: {max_drawdown*100}%")
    
    def _register_events(self):
        """Register event handlers"""
        self.event_bus.subscribe(EventType.SIGNAL_GENERATED, self._handle_signal)
        self.event_bus.subscribe(EventType.ORDER_PLACED, self._handle_order_placed)
        self.event_bus.subscribe(EventType.ORDER_FILLED, self._handle_order_filled)
        self.event_bus.subscribe(EventType.ERROR, self._handle_error)
    
    def _handle_signal(self, signal: Signal) -> None:
        """
        Handle incoming trading signals
        
        Args:
            signal: Trading signal to process
        """
        try:
            self.logger.info(f"Received signal: {signal}")
            
            # Handle close signals from spot strategies
            if signal.type == 'close' and signal.strategy_type == 'spot':
                # Get current position
                position = self.risk_manager.get_position(signal.symbol)
                
                if position:
                    # Calculate position value in USD
                    position_value = position.amount * position.current_price
                    
                    # Skip if position value is too small
                    if position_value <= 1.0:
                        self.logger.warning(
                            f"Skipping close signal for {signal.symbol} - "
                            f"position value (${position_value:.2f}) is too small"
                        )
                        return
                    
                    # Determine side based on position
                    side = 'sell' if position.side == 'long' else 'buy'
                    
                    # Create market order to close position
                    order = Order(
                        symbol=signal.symbol,
                        side=side,
                        type='market',
                        amount=position.amount,
                        price=None,
                        params={'reduceOnly': True}
                    )
                    
                    # Execute order
                    result = self.executor.place_order(order)
                    
                    if result:
                        self.logger.info(
                            f"Position closed for {signal.symbol}: "
                            f"{position.amount:.8f} units at {position.current_price:.6f}, "
                            f"value=${position_value:.2f}"
                        )
                        self.event_bus.publish(EventType.ORDER_PLACED, result)
                    else:
                        self.logger.error(f"Failed to close position for {signal.symbol}")
                        
            # Handle buy/sell signals
            elif signal.type in ['buy', 'sell']:
                # Validate signal with risk manager
                validation_result = self.risk_manager.validate_signal(signal)
                
                if not validation_result.is_valid:
                    self.logger.info(f"Signal rejected: {validation_result.reason}")
                    return
                
                # Calculate position size
                position_size = self.risk_manager.calculate_position_size(signal)
                
                if position_size <= 0:
                    self.logger.warning(f"Invalid position size calculated for {signal.symbol}: {position_size}")
                    return
                
                # Create market order
                order = Order(
                    symbol=signal.symbol,
                    side=signal.type,
                    type='market',
                    amount=position_size,
                    price=None
                )
                
                # Execute order
                result = self.executor.place_order(order)
                
                if result:
                    self.logger.info(
                        f"Order executed for {signal.symbol}: "
                        f"{signal.type.upper()} {position_size:.8f} units"
                    )
                    self.event_bus.publish(EventType.ORDER_PLACED, result)
                else:
                    self.logger.error(f"Failed to execute {signal.type} order for {signal.symbol}")
                    
        except Exception as e:
            self.logger.error(f"Error handling signal: {e}")
    
    def _handle_order_placed(self, event: Event):
        """Handle order placed event"""
        order = event.data.get('order')
        signal = event.data.get('signal')
        self.logger.info(f"Order placed successfully: {order.get('id')}")
    
    def _handle_order_filled(self, event: Event):
        """Handle order filled event"""
        order = event.data.get('order')
        self.logger.info(f"Order filled: {order.get('id')}")
    
    def _handle_error(self, event: Event):
        """Handle error event"""
        source = event.data.get('source', 'unknown')
        message = event.data.get('message', 'No details')
        self.logger.error(f"Error in {source}: {message}")
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
    
    def run(self):
        """Run the trading bot"""
        self.running = True
        self.logger.info("Starting trading bot...")
        
        # Publish startup event
        self.event_bus.publish(Event(
            EventType.STARTUP,
            {'timestamp': time.time()}
        ))
        
        # Get drawdown check interval - required in config
        drawdown_check_interval = self.config.get_strict('risk.drawdown_check_interval')
        last_drawdown_check = 0
        
        # Internal retry interval - OK to have a default
        retry_interval = 60  # This is an internal parameter, not in config
        last_retry_check = 0
        
        # Track last signal check time for each timeframe
        last_signal_check = {}
        # Map timeframes to seconds for throttling
        timeframe_seconds = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '1h': 3600,
            '4h': 14400,
            '1d': 86400
        }
        
        try:
            while self.running:
                # Process each trading symbol
                current_time = time.time()
                
                for symbol in self.strategies.keys():
                    # Skip if key isn't in strategies (shouldn't happen, but better be safe)
                    if symbol not in self.strategies:
                        continue
                    
                    # Determine timeframe from strategy
                    timeframe = getattr(self.strategies[symbol], 'timeframe', '1h')
                    
                    # Only check for signals at appropriate intervals based on timeframe
                    # Convert timeframe to seconds and add a small buffer (5 seconds)
                    check_interval = timeframe_seconds.get(timeframe, 3600) + 5  # Default to 1h if unknown
                    
                    # Create a key that combines symbol and timeframe for tracking last check time
                    symbol_timeframe_key = f"{symbol}_{timeframe}"
                    
                    # Initialize last check time if not set
                    if symbol_timeframe_key not in last_signal_check:
                        last_signal_check[symbol_timeframe_key] = 0
                    
                    # Skip if we checked too recently
                    if current_time - last_signal_check[symbol_timeframe_key] < check_interval:
                        self.logger.debug(
                            f"Skipping signal check for {symbol} - next check in "
                            f"{check_interval - (current_time - last_signal_check[symbol_timeframe_key]):.0f} seconds"
                        )
                        continue
                    
                    # Update the last check time
                    last_signal_check[symbol_timeframe_key] = current_time
                    
                    # Fetch latest market data
                    try:
                        # Get required data points from strategy
                        required_candles = getattr(self.strategies[symbol], 'get_required_data_points', lambda: 100)()
                        
                        # Fetch candles
                        candles = self.data_provider.get_historical_data(
                            symbol=symbol,
                            timeframe=timeframe,
                            limit=required_candles
                        )
                        
                        # Skip if not enough candles
                        if len(candles) < required_candles:
                            self.logger.warning(f"Not enough candles for {symbol}: {len(candles)}/{required_candles}")
                            continue
                        
                        # Generate signals from strategy
                        signals = self.strategies[symbol].generate_signals(candles)
                        
                        # Process signals
                        for signal in signals:
                            # Publish signal event
                            self.event_bus.publish(Event(
                                EventType.SIGNAL_GENERATED,
                                signal
                            ))
                            
                    except Exception as e:
                        self.logger.error(f"Error processing {symbol}: {e}")
                
                # Check for drawdown limit breaches at regular intervals
                if current_time - last_drawdown_check > drawdown_check_interval:
                    self.logger.debug("Checking positions against drawdown limits")
                    symbols_to_close = self.risk_manager.check_drawdown_limits()
                    
                    # Generate close signals for positions that breached drawdown limits
                    for symbol in symbols_to_close:
                        self.logger.warning(f"Maximum drawdown exceeded for {symbol}, generating close signal")
                        
                        # Get position details 
                        position = self.risk_manager.get_position(symbol)
                        
                        # If position doesn't exist, try to check spot balance directly
                        if position is None:
                            # Extract base currency from symbol
                            base_currency = symbol.split('/')[0]
                            
                            try:
                                # Directly check balance from exchange
                                balance = self.data_provider.exchange.fetch_balance()
                                free_amount = float(balance.get(base_currency, {}).get('free', 0) or 0)
                                
                                if free_amount > 0:
                                    # We have a balance, we can directly close this position
                                    self.logger.info(f"Found {base_currency} balance directly: {free_amount}")
                                    
                                    try:
                                        # Create an order to close the position
                                        order = Order(
                                            symbol=symbol,
                                            order_type='market',
                                            side='sell',  # Spot positions are always closed with sell
                                            amount=free_amount,
                                            strategy="risk_management",  # Add source of order
                                            signal_price=0  # No signal price for risk management orders
                                        )
                                        
                                        # Execute order
                                        order_result = self.executor.place_order(order)
                                        self.logger.info(f"Position closed due to max drawdown: {order_result}")
                                        
                                        # Publish order placed event
                                        self.event_bus.publish(Event(
                                            EventType.ORDER_PLACED,
                                            {
                                                'signal': None,  # No signal for this order
                                                'order': order_result,
                                                'reason': 'max_drawdown'
                                            }
                                        ))
                                        
                                        # If this symbol was in retry list, remove it
                                        if hasattr(self, '_drawdown_close_retries') and symbol in self._drawdown_close_retries:
                                            del self._drawdown_close_retries[symbol]
                                            
                                        continue  # Skip to next symbol
                                    except Exception as e:
                                        self.logger.error(f"Error closing position due to max drawdown: {e}")
                                        # Add to retry list with timestamp
                                        if hasattr(self, '_drawdown_close_retries'):
                                            self._drawdown_close_retries[symbol] = current_time
                            except Exception as e:
                                self.logger.error(f"Error checking balance for {base_currency}: {e}")
                        
                        # If we have a position object, proceed with normal close
                        if position and position.amount > 0:
                            try:
                                # Determine the proper side for closing the position
                                close_side = 'sell' if position.side.lower() == 'long' else 'buy'
                                
                                # Create an order to close the position
                                order = Order(
                                    symbol=symbol,
                                    order_type='market',
                                    side=close_side,  # Use appropriate side based on position type
                                    amount=position.amount
                                )
                                
                                # Execute order
                                order_result = self.executor.place_order(order)
                                self.logger.info(f"Position closed due to max drawdown: {order_result}")
                                
                                # Publish order placed event
                                self.event_bus.publish(Event(
                                    EventType.ORDER_PLACED,
                                    {
                                        'signal': None,  # No signal for this order
                                        'order': order_result,
                                        'reason': 'max_drawdown'
                                    }
                                ))
                                
                                # Remove from retry list if it was there
                                if symbol in self._drawdown_close_retries:
                                    del self._drawdown_close_retries[symbol]
                                    
                            except Exception as e:
                                self.logger.error(f"Error closing position due to max drawdown: {e}")
                                
                                # Add to retry list with timestamp
                                self._drawdown_close_retries[symbol] = current_time
                    
                    # Update last check time
                    last_drawdown_check = current_time
                
                # Check if we need to retry any failed drawdown close orders
                if self._drawdown_close_retries and current_time - last_retry_check > retry_interval:
                    self.logger.debug(f"Retrying {len(self._drawdown_close_retries)} failed drawdown close orders")
                    
                    # Create a copy of keys to allow modification during iteration
                    symbols_to_retry = list(self._drawdown_close_retries.keys())
                    
                    for symbol in symbols_to_retry:
                        # Get position details 
                        position = self.risk_manager.get_position(symbol)
                        if position and position.amount > 0:
                            try:
                                # Determine the proper side for closing
                                close_side = 'sell' if position.side.lower() == 'long' else 'buy'
                                
                                # Create an order to close the position
                                order = Order(
                                    symbol=symbol,
                                    order_type='market',
                                    side=close_side,
                                    amount=position.amount
                                )
                                
                                # Execute order
                                order_result = self.executor.place_order(order)
                                self.logger.info(f"Position closed on retry (drawdown limit): {order_result}")
                                
                                # Publish order placed event
                                self.event_bus.publish(Event(
                                    EventType.ORDER_PLACED,
                                    {
                                        'signal': None,
                                        'order': order_result,
                                        'reason': 'max_drawdown_retry'
                                    }
                                ))
                                
                                # Remove from retry list
                                del self._drawdown_close_retries[symbol]
                                
                            except Exception as e:
                                self.logger.error(f"Retry failed for drawdown close of {symbol}: {e}")
                                # Keep in retry list for next attempt
                        else:
                            # Position no longer exists or is empty, remove from retry list
                            self.logger.info(f"Position {symbol} no longer exists, removing from retry list")
                            del self._drawdown_close_retries[symbol]
                    
                    # Update last retry check time
                    last_retry_check = current_time
                
                # Throttle the loop to avoid excessive CPU usage
                time.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
            # Publish error event
            self.event_bus.publish(Event(
                EventType.ERROR,
                {
                    'source': 'main_loop',
                    'message': str(e)
                }
            ))
            
        finally:
            # Clean shutdown
            self.logger.info("Trading bot stopped")
    
    def stop(self):
        """Stop the trading bot"""
        if not self.running:
            return
            
        self.running = False
        self.logger.info("Stopping trading bot...")
        
        # Publish shutdown event
        self.event_bus.publish(Event(
            EventType.SHUTDOWN,
            {'timestamp': time.time()}
        ))
        
        # You could add cleanup code here
        # e.g., close positions, cancel open orders

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Trading Bot')
    parser.add_argument('--config', type=str, required=True, help='Path to configuration file')
    args = parser.parse_args()
    
    bot = TradingBot(config_path=args.config)
    bot.run()