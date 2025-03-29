# trading_bot/trading/position_monitor.py
import time
from typing import Dict, Any, List, Optional
import logging

from trading_bot.utils.events import EventBus, EventType, Event
from trading_bot.models.data_models import Order, Position

class PositionMonitor:
    """
    Monitors positions, handles drawdown checks, and manages position-related events
    """
    
    def __init__(self, event_bus, risk_manager, executor, config):
        """
        Initialize the position monitor
        
        Args:
            event_bus: Event bus for publishing and subscribing to events
            risk_manager: Risk manager for checking drawdown and positions
            executor: Order executor for placing orders
            config: Configuration object
        """
        self.event_bus = event_bus
        self.risk_manager = risk_manager
        self.executor = executor
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Register for order events
        self.event_bus.subscribe(EventType.ORDER_PLACED, self._handle_order_placed)
        self.event_bus.subscribe(EventType.ORDER_FILLED, self._handle_order_filled)
        
        # Register for system events
        self.event_bus.subscribe(EventType.STARTUP, self._handle_startup)
        
        self.logger.info("PositionMonitor initialized")
    
    def _handle_startup(self, event: Event) -> None:
        """
        Handle system startup event
        
        Args:
            event: Startup event
        """
        # Initialize positions on startup
        self.risk_manager.position_tracker.update_positions()
        positions = self.risk_manager.position_tracker.get_all_positions()
        
        if positions:
            self.logger.info(f"Found {len(positions)} existing positions at startup")
            for position in positions:
                # Update position with current price
                ticker = self.risk_manager.position_tracker.exchange.fetch_ticker(position.symbol)
                current_price = float(ticker['last'])
                position.update_price(current_price)
                
                self.logger.info(
                    f"Position: {position.symbol} - {position.side} {position.amount:.8f} "
                    f"@ {position.entry_price:.6f} (current: {position.current_price:.6f}, "
                    f"PnL: {position.unrealized_pnl:.2f}, "
                    f"Profit: {position.profit_percentage*100:.2f}%, "
                    f"Drawdown: {position.current_drawdown_percentage*100:.2f}%, "
                    f"Duration: {position.duration})"
                )
        else:
            self.logger.info("No existing positions at startup")
    
    def _handle_order_placed(self, event: Event) -> None:
        """
        Handle order placed events
        
        Args:
            event: Order placed event
        """
        order_data = event.data.get('order', {})
        signal = event.data.get('signal')
        
        # Extract order ID and other info
        order_id = order_data.get('id', 'unknown')
        symbol = order_data.get('symbol', 'unknown')
        
        # Log the order with more context
        if signal:
            self.logger.info(
                f"Order placed: {order_id} for {symbol} - "
                f"Signal type: {signal.signal_type} "
                f"from strategy: {signal.strategy_name}"
            )
        else:
            reason = event.data.get('reason', 'unknown')
            self.logger.info(
                f"Order placed: {order_id} for {symbol} - "
                f"Reason: {reason}"
            )
    
    def _handle_order_filled(self, event: Event) -> None:
        """
        Handle order filled events
        
        Args:
            event: Order filled event
        """
        order_data = event.data.get('order', {})
        trade_data = event.data.get('trade', {})
        
        # Extract order and trade info
        order_id = order_data.get('id', 'unknown')
        symbol = order_data.get('symbol', 'unknown')
        side = order_data.get('side', 'unknown')
        
        # Log the filled order
        self.logger.info(
            f"Order filled: {order_id} for {symbol} - "
            f"Side: {side}"
        )
        
        # Update positions after an order is filled
        self.risk_manager.position_tracker.update_positions()
        
        # Log the updated position if available
        position = self.risk_manager.get_position(symbol)
        if position:
            self.logger.info(
                f"Updated position for {symbol}: "
                f"{position.side} {position.amount:.8f} @ {position.entry_price:.6f} "
                f"(current: {position.current_price:.6f})"
            )
    
    def update_position_metadata(self, position: Position) -> None:
        """
        Update additional metadata for a position
        
        Args:
            position: Position to update
        """
        # Duration
        duration = position.duration
        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        # Calculate drawdown and profit
        drawdown = position.current_drawdown_percentage
        profit = position.profit_percentage
        
        # Log position status with enhanced details
        self.logger.info(
            f"Position status: {position.symbol} {position.side} - "
            f"Age: {int(hours)}h {int(minutes)}m, "
            f"Amount: {position.amount:.8f}, "
            f"Entry: {position.entry_price:.6f}, "
            f"Current: {position.current_price:.6f}, "
            f"Drawdown: {drawdown*100:.2f}%, "
            f"Profit: {profit*100:.2f}%"
        )
    
    def check_all_positions(self) -> None:
        """
        Check all positions and update their status
        """
        # Update all positions
        self.risk_manager.position_tracker.update_positions()
        
        # Get all positions
        positions = self.risk_manager.position_tracker.get_all_positions()
        
        for position in positions:
            self.update_position_metadata(position) 