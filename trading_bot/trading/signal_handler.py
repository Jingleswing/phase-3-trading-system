# trading_bot/trading/signal_handler.py
from typing import Dict, Any
import logging

from trading_bot.utils.events import EventBus, EventType, Event
from trading_bot.models.data_models import Signal, Order
from trading_bot.interfaces.risk_manager import RiskManager
from trading_bot.interfaces.order_executor import OrderExecutor

class SignalHandler:
    def __init__(self, event_bus: EventBus, risk_manager: RiskManager, executor: OrderExecutor):
        self.event_bus = event_bus
        self.risk_manager = risk_manager
        self.executor = executor
        self.logger = logging.getLogger(__name__)
        
        # Subscribe to signals
        self.event_bus.subscribe(EventType.SIGNAL_GENERATED, self._handle_signal)
        
    def _handle_signal(self, event: Event):
        """Handle trading signals"""
        try:
            # Create Signal object from event data
            signal = Signal(
                symbol=event.data['symbol'],
                timestamp=event.data['timestamp'],
                signal_type=event.data['signal_type'],
                price=event.data['price'],
                strategy_name=event.data['strategy_name'],
                params=event.data.get('params', {}),
                strength=event.data.get('strength', 1.0)
            )
            
            # Log signal details
            self.logger.info(
                f"Processing {signal.signal_type} signal for {signal.symbol} "
                f"(Strategy: {signal.strategy_name})"
            )
            
            # Validate signal with risk manager
            if not self.risk_manager.validate_signal(signal):
                return
                
            # Execute order
            order = self.executor.execute_order(signal)
            
            # Log execution result
            self.logger.info(
                f"Order executed: {order.symbol} {order.order_type} {order.amount:.8f} "
                f"at {order.price:.8f if order.price else 'market'} (ID: {order.id})"
            )
            
            # Publish order event
            self.event_bus.publish(Event(
                type=EventType.ORDER_PLACED,
                data={'order': order}
            ))
            
        except Exception as e:
            self.logger.error(f"Error processing signal: {e}")
            self.event_bus.publish(Event(
                type=EventType.ERROR,
                data={
                    'type': 'signal_processing_error',
                    'symbol': event.data.get('symbol', 'unknown'),
                    'error': str(e)
                }
            ))
    
    def _handle_close_signal(self, signal: Signal) -> None:
        """
        Handle close signals to exit positions
        
        Args:
            signal: Close signal
        """
        # Get current position
        position = self.risk_manager.get_position(signal.symbol)
        
        if not position:
            self.logger.info(f"No position found for {signal.symbol}, nothing to close")
            return
            
        # Calculate position value in USD
        position_value = position.amount * position.current_price
        
        # Skip if position value is too small (dust position)
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
            order_type='market',
            side=side,
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
            
            # Publish order placed event
            self.event_bus.publish(Event(
                type=EventType.ORDER_PLACED,
                data={
                    "order": result,
                    "signal": signal,
                    "reason": signal.params.get('reason', 'signal')
                }
            ))
        else:
            self.logger.error(f"Failed to close position for {signal.symbol}")
    
    def _handle_trade_signal(self, signal: Signal) -> None:
        """
        Handle buy/sell signals to enter positions
        
        Args:
            signal: Buy or sell signal
        """
        # Validate signal with risk manager
        is_valid, reason = self.risk_manager.validate_signal(signal)
        
        if not is_valid:
            self.logger.info(f"Signal rejected: {reason}")
            return
        
        # Calculate position size
        position_size = self.risk_manager.calculate_position_size(signal)
        
        if position_size <= 0:
            self.logger.warning(f"Invalid position size calculated for {signal.symbol}: {position_size}")
            return
        
        # Create market order
        order = Order(
            symbol=signal.symbol,
            order_type='market',
            side=signal.signal_type,
            amount=position_size,
            price=None,
            strategy=signal.strategy_name,
            signal_price=signal.price
        )
        
        # Execute order
        result = self.executor.place_order(order)
        
        if result:
            self.logger.info(
                f"Order executed for {signal.symbol}: "
                f"{signal.signal_type.upper()} {position_size:.8f} units at ~{signal.price:.6f}"
            )
            
            # Publish order placed event
            self.event_bus.publish(Event(
                type=EventType.ORDER_PLACED,
                data={
                    "order": result,
                    "signal": signal
                }
            ))
        else:
            self.logger.error(f"Failed to execute {signal.signal_type} order for {signal.symbol}") 