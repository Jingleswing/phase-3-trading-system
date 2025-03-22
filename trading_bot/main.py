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
        default_config_path = os.path.join(os.path.dirname(__file__), 'config', 'default_config.yaml')
        self.config = Config(config_path, default_config_path)
        
        # Set up logging
        log_level = self.config.get('system.log_level', 'INFO')
        setup_logging(level=log_level)
        
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
        
        # Set up strategy
        strategy_config = self.config.get('strategy', {})
        self.strategy = StrategyFactory.create_strategy(strategy_config)
        
        # Set up order executor
        trading_enabled = self.config.get('trading.enabled', False)
        dry_run = not trading_enabled
        self.executor = CCXTExecutor(
            exchange=self.data_provider.exchange,
            dry_run=dry_run
        )
        
        # Set up risk manager
        risk_config = self.config.get('risk', {})
        self.risk_manager = BasicRiskManager(
            exchange=self.data_provider.exchange,
            risk_per_trade=risk_config.get('risk_per_trade', 0.02),
            max_open_trades=risk_config.get('max_open_trades', 3),
            stop_loss_pct=risk_config.get('stop_loss_pct', 0.05)
        )
    
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
            
            # Set stop loss if needed
            if signal.signal_type == 'buy' and not self.executor.dry_run:
                stop_loss = self.risk_manager.set_stop_loss(signal)
                if stop_loss:
                    # Update stop loss amount
                    stop_loss.amount = position_size
                    
                    # Place stop loss order
                    try:
                        sl_result = self.executor.place_order(stop_loss)
                        self.logger.info(f"Stop loss order placed: {sl_result}")
                    except Exception as e:
                        self.logger.error(f"Error placing stop loss order: {e}")
        
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
        
        # Get trading parameters
        symbols = self.config.get('trading.symbols', ['ETH/USDT'])
        timeframe = self.config.get('trading.timeframe', '1m')
        loop_interval = self.config.get('system.loop_interval', 60)
        
        self.logger.info(f"Trading {symbols} on {timeframe} timeframe")
        
        try:
            while self.running:
                for symbol in symbols:
                    try:
                        # Fetch latest data
                        data = self.data_provider.get_historical_data(
                            symbol=symbol,
                            timeframe=timeframe,
                            limit=100  # Fetch enough data for indicators
                        )
                        
                        if len(data) < 50:  # Make sure we have enough data
                            self.logger.warning(f"Not enough data for {symbol}, skipping")
                            continue
                        
                        # Generate signals
                        signals = self.strategy.generate_signals(data)
                        
                        # Process signals
                        for signal in signals:
                            self.event_bus.publish(Event(
                                EventType.SIGNAL_GENERATED,
                                signal
                            ))
                    
                    except Exception as e:
                        self.logger.error(f"Error processing {symbol}: {e}")
                        
                        # Publish error event
                        self.event_bus.publish(Event(
                            EventType.ERROR,
                            {
                                'source': 'data_processing',
                                'message': str(e),
                                'symbol': symbol
                            }
                        ))
                
                # Sleep until next iteration
                time.sleep(loop_interval)
                
        except Exception as e:
            self.logger.critical(f"Unhandled exception: {e}")
        finally:
            self.stop()
    
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
    parser.add_argument('--config', type=str, default=None, help='Path to configuration file')
    args = parser.parse_args()
    
    bot = TradingBot(config_path=args.config)
    bot.run()