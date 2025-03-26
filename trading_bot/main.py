# trading_bot/main.py
import time
import argparse
import os
import signal
import sys
from typing import Dict, Any

from trading_bot.utils.config import Config
from trading_bot.utils.logging import setup_logging, LoggerMixin
from trading_bot.utils.events import EventBus, EventType, Event

from trading_bot.data.providers.ccxt_provider import CCXTProvider
from trading_bot.strategies.factory import StrategyFactory
from trading_bot.execution.ccxt_executor import CCXTExecutor
from trading_bot.risk.basic_risk_manager import BasicRiskManager
from trading_bot.models.data_models import Order

class TradingBot(LoggerMixin):
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
        
        # Set up logging with config
        setup_logging(config=self.config.config)
        
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
        
        self.logger.info("Trading bot initialized")
    
    def _setup_components(self):
        """Set up all bot components based on configuration"""
        # Set up data provider
        exchange_id = self.config.get('exchange.id', 'bybit')
        api_key = self.config.get('exchange.api_key')
        secret = self.config.get('exchange.secret')
        params = self.config.get('exchange.params', {})
        
        self.data_provider = CCXTProvider(
            exchange_id=exchange_id,
            api_key=api_key,
            secret=secret,
            params=params
        )
        
        # Create strategies for different market types
        self.strategies = {}
        
        # Get trading symbols
        trading_symbols = self.config.get('trading.symbols', [])
        
        # Count total trading pairs for position sizing
        total_trading_pairs = len(trading_symbols)
        self.logger.info(f"Total trading pairs: {total_trading_pairs}")
        
        for symbol_config in trading_symbols:
            if isinstance(symbol_config, dict):
                symbol = symbol_config.get('symbol')
                market_type = symbol_config.get('market_type')
                
                # Get strategy configuration from config file
                strategy_config = self.config.get('strategy', {})
                
                # Create the strategy
                self.strategies[symbol] = StrategyFactory.create_strategy(strategy_config)
                self.logger.info(f"Created {market_type} strategy for {symbol}")
            else:
                # If symbol is just a string, assume it's a spot market
                strategy_config = self.config.get('strategy', {})
                self.strategies[symbol_config] = StrategyFactory.create_strategy(strategy_config)
                self.logger.info(f"Created spot strategy for {symbol_config}")
        
        # Check if any valid strategies were created
        if not self.strategies:
            self.logger.warning("No valid trading strategies configured")
        
        # Set up order executor
        trading_enabled = self.config.get('trading.enabled', False)
        dry_run = not trading_enabled
        self.executor = CCXTExecutor(
            exchange=self.data_provider.exchange,
            dry_run=dry_run
        )
        
        # Set up risk manager with total trading pairs and max drawdown
        max_drawdown = self.config.get('risk.max_drawdown', 0.25)  # Default 25% max drawdown
        self.risk_manager = BasicRiskManager(
            exchange=self.data_provider.exchange,
            max_open_trades=total_trading_pairs,  # Use total trading pairs as max open trades
            max_drawdown=max_drawdown
        )
        
        self.logger.info(f"Risk manager configured with max drawdown: {max_drawdown*100}%")
    
    def _register_events(self):
        """Register event handlers"""
        self.event_bus.subscribe(EventType.SIGNAL_GENERATED, self._handle_signal)
        self.event_bus.subscribe(EventType.ORDER_PLACED, self._handle_order_placed)
        self.event_bus.subscribe(EventType.ORDER_FILLED, self._handle_order_filled)
        self.event_bus.subscribe(EventType.ERROR, self._handle_error)
    
    def _handle_signal(self, event: Event):
        """Handle a signal event"""
        signal = event.data
        self.logger.info(f"Received signal: {signal.signal_type} {signal.symbol} at {signal.price}")
        
        # Special handling for "close" signals from spot strategies
        if signal.signal_type == 'close':
            # Find existing position for this symbol
            position = self.risk_manager.get_position(signal.symbol)
            if position is None or position.amount == 0:
                self.logger.warning(f"Received close signal for {signal.symbol} but no position exists")
                return
                
            # Create an order to close the position
            order = Order(
                symbol=signal.symbol,
                order_type='market',
                side='sell',  # Use 'sell' for the actual order execution to close the position
                amount=position.amount
            )
            
            try:
                order_result = self.executor.place_order(order)
                self.logger.info(f"Position closed: {order_result}")
                
                # Publish order placed event
                self.event_bus.publish(Event(
                    EventType.ORDER_PLACED,
                    {
                        'signal': signal,
                        'order': order_result
                    }
                ))
            except Exception as e:
                self.logger.error(f"Error closing position: {e}")
                # Publish error event
                self.event_bus.publish(Event(
                    EventType.ERROR,
                    {
                        'source': 'order_execution',
                        'message': str(e),
                        'signal': signal
                    }
                ))
            return
        
        # Continue with existing code for buy/sell signals
        # Validate signal with risk manager
        valid, reason = self.risk_manager.validate_signal(signal)
        if not valid:
            self.logger.warning(f"Signal rejected by risk manager: {reason}")
            return
        
        # Calculate position size
        position_size = self.risk_manager.calculate_position_size(signal)
        if position_size <= 0:
            self.logger.warning(f"Position size is zero or negative, skipping order")
            return
        
        # Create order
        order = Order(
            symbol=signal.symbol,
            order_type='market',
            side=signal.signal_type,  # 'buy' or 'sell'
            amount=position_size
        )
        
        # Execute order
        try:
            order_result = self.executor.place_order(order)
            self.logger.info(f"Order placed: {order_result}")
            
            # Publish order placed event
            self.event_bus.publish(Event(
                EventType.ORDER_PLACED,
                {
                    'signal': signal,
                    'order': order_result
                }
            ))
        
        except Exception as e:
            self.logger.error(f"Error executing order: {e}")
            
            # Publish error event
            self.event_bus.publish(Event(
                EventType.ERROR,
                {
                    'source': 'order_execution',
                    'message': str(e),
                    'signal': signal
                }
            ))
    
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
        
        # Interval for checking drawdown (in seconds)
        drawdown_check_interval = self.config.get('risk.drawdown_check_interval', 300)  # Default 5 minutes
        last_drawdown_check = 0
        
        try:
            while self.running:
                # Process each trading symbol
                for symbol in self.strategies.keys():
                    # Skip if key isn't in strategies (shouldn't happen, but better be safe)
                    if symbol not in self.strategies:
                        continue
                    
                    # Fetch latest market data
                    try:
                        # Determine timeframe from strategy
                        timeframe = getattr(self.strategies[symbol], 'timeframe', '1h')
                        
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
                current_time = time.time()
                if current_time - last_drawdown_check > drawdown_check_interval:
                    self.logger.debug("Checking positions against drawdown limits")
                    symbols_to_close = self.risk_manager.check_drawdown_limits()
                    
                    # Generate close signals for positions that breached drawdown limits
                    for symbol in symbols_to_close:
                        self.logger.warning(f"Maximum drawdown exceeded for {symbol}, generating close signal")
                        
                        # Get position details 
                        position = self.risk_manager.get_position(symbol)
                        if position and position.amount > 0:
                            try:
                                # Create an order to close the position
                                order = Order(
                                    symbol=symbol,
                                    order_type='market',
                                    side='sell',  # Use 'sell' for spot positions
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
                            except Exception as e:
                                self.logger.error(f"Error closing position due to max drawdown: {e}")
                    
                    # Update last check time
                    last_drawdown_check = current_time
                
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