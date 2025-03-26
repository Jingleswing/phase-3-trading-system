# trading_bot/risk/basic_risk_manager.py
from typing import Dict, Tuple, Any, Optional, List
from trading_bot.interfaces.risk_manager import RiskManager
from trading_bot.models.data_models import Signal, Order, Position, PositionTracker
from trading_bot.utils.logging import LoggerMixin

class BasicRiskManager(RiskManager, LoggerMixin):
    """
    Basic risk management implementation that uses equal division sizing
    based on total number of trading pairs.
    """
    
    def __init__(self, 
                 exchange,  # CCXT exchange instance
                 max_open_trades: int,  # Maximum number of open trades
                 max_drawdown: float = 0.25): # Maximum drawdown allowed (25% default)
        """
        Initialize the risk manager
        
        Args:
            exchange: CCXT exchange instance for account info
            max_open_trades: Maximum number of open trades (equal to total trading pairs)
            max_drawdown: Maximum drawdown allowed before closing a position (as a decimal, e.g., 0.25 = 25%)
        """
        self.exchange = exchange
        self.max_open_trades = max_open_trades
        self.max_drawdown = max_drawdown
        self.position_tracker = PositionTracker(exchange)
        
        self.logger.info(
            f"Initialized BasicRiskManager with max_open_trades={max_open_trades}, "
            f"max_drawdown={max_drawdown*100}%"
        )
    
    def validate_signal(self, signal: Signal) -> Tuple[bool, str]:
        """
        Validate if a signal should be executed based on risk rules
        
        Args:
            signal: Signal to validate
            
        Returns:
            (valid, reason) tuple where valid is a boolean and reason is a string
        """
        # For close signals, always validate them
        if signal.signal_type == 'close':
            return True, "Close signals are always valid"

        # Update our position tracker to get latest data
        self.position_tracker.update_positions()
        current_positions = self.position_tracker.get_all_positions()

        # Check if we already have too many open trades
        if len(current_positions) >= self.max_open_trades:
            reason = f"Maximum number of open trades reached ({self.max_open_trades})"
            self.logger.warning(f"Signal rejected: {reason}")
            return False, reason
            
        # For buy signals, check if the sell MA configuration would already trigger a close
        # This prevents opening positions that are already in a sell configuration
        if signal.signal_type == 'buy' and signal.params is not None:
            if 'sell_short_period' in signal.params and 'sell_long_period' in signal.params:
                # Try to get sell MA information from signal params if available
                sell_short_value = signal.params.get('sell_short_ma_value')
                sell_long_value = signal.params.get('sell_long_ma_value')
                
                # If sell MA values are available, check if they're in a sell configuration
                if sell_short_value is not None and sell_long_value is not None:
                    if sell_short_value < sell_long_value:
                        reason = "Sell MAs already in sell configuration, skip this buy"
                        self.logger.warning(f"Signal rejected: {reason}")
                        return False, reason
        
        return True, "Signal validated"
    
    def calculate_position_size(self, signal: Signal) -> float:
        """
        Calculate position size using available USDT balance divided by
        remaining positions (max_open_trades - current positions).
        
        Args:
            signal: Trading signal
            
        Returns:
            Position size in base currency
        """
        try:
            # Update our position tracker to get latest data
            self.position_tracker.update_positions()
            
            # Get account balance
            balance = self.exchange.fetch_balance()
            
            # For simplicity, assuming we're trading against USDT
            quote_currency = signal.symbol.split('/')[1]  # e.g., 'USDT' from 'ETH/USDT'
            available_balance = balance.get(quote_currency, {}).get('free', 0)
            
            if available_balance <= 0:
                self.logger.warning(f"No available balance in {quote_currency}")
                return 0
            
            # Count active positions to determine how many positions we already have
            active_positions = len(self.position_tracker.get_all_positions())
            
            # Calculate remaining available positions
            remaining_positions = max(1, self.max_open_trades - active_positions)
            
            # Calculate amount to use based on remaining positions
            amount_to_use = available_balance / remaining_positions
            self.logger.info(
                f"Position sizing based on remaining positions: {amount_to_use} {quote_currency} "
                f"(1/{remaining_positions} of {available_balance}, with {active_positions} active positions)"
            )
            
            # Calculate position size based on price
            position_size = amount_to_use / signal.price
            
            # Apply leverage for futures markets if specified
            market_type = signal.params.get('market_type', 'spot')
            if market_type == 'futures' and 'leverage' in signal.params:
                leverage = signal.params.get('leverage', 1)
                position_size = position_size * leverage
                self.logger.info(f"Applied {leverage}x leverage to position size")
            
            self.logger.info(f"Calculated position size: {position_size} {signal.symbol.split('/')[0]}")
            
            return position_size
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0  # Return 0 on error to prevent trading
    
    def check_drawdown_limits(self) -> List[str]:
        """
        Check all open positions against drawdown limits
        
        Returns:
            List of symbols that have exceeded the maximum drawdown limit
        """
        self.position_tracker.update_positions()
        positions = self.position_tracker.get_all_positions()
        
        symbols_to_close = []
        for position in positions:
            drawdown = position.current_drawdown_percentage
            if drawdown > self.max_drawdown:
                self.logger.warning(
                    f"Position {position.symbol} has exceeded maximum drawdown: "
                    f"{drawdown*100:.2f}% > {self.max_drawdown*100:.2f}%"
                )
                symbols_to_close.append(position.symbol)
                
        return symbols_to_close
    
    def set_stop_loss(self, signal: Signal) -> Optional[Order]:
        """
        This method is required by the RiskManager interface but is not implemented
        We're using the check_drawdown_limits method instead for dynamic risk management
        
        Args:
            signal: Trading signal
            
        Returns:
            None as stop loss is disabled
        """
        return None
        
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get current position for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Position object or None if no position exists
        """
        # Update positions before returning
        self.position_tracker.update_positions()
        return self.position_tracker.get_position(symbol)