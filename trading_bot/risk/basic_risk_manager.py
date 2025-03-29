# trading_bot/risk/basic_risk_manager.py
from typing import Dict, Tuple, Any, Optional, List
from trading_bot.interfaces.risk_manager import RiskManager
from trading_bot.models.data_models import Signal, Order, Position, PositionTracker
import logging
from trading_bot.utils.symbol_utils import normalize_symbol, get_base_currency, get_quote_currency

class BasicRiskManager(RiskManager):
    """
    Basic risk management implementation that uses equal division sizing
    based on total number of trading pairs.
    """
    
    def __init__(self, 
                 exchange,  # CCXT exchange instance
                 max_open_trades: int,  # Maximum number of open trades
                 max_drawdown: float = 0.25, # Maximum drawdown allowed (25% default)
                 position_tracker: PositionTracker = None, # Keep position_tracker
                 event_bus = None, # Add event_bus
                 config: Dict[str, Any] = None): # Add config
        """
        Initialize the risk manager
        
        Args:
            exchange: CCXT exchange instance for account info
            max_open_trades: Maximum number of open trades (equal to total trading pairs)
            max_drawdown: Maximum drawdown allowed before closing a position (as a decimal, e.g., 0.25 = 25%)
            position_tracker: Shared PositionTracker instance
            event_bus: EventBus instance for publishing events
            config: Risk configuration dictionary
        """
        self.exchange = exchange
        if position_tracker is None:
            raise ValueError("PositionTracker instance must be provided to BasicRiskManager")
        self.position_tracker = position_tracker # Assign injected tracker
        self.logger = logging.getLogger(__name__)
        self.max_open_trades = max_open_trades
        self.max_drawdown = max_drawdown
        self.event_bus = event_bus # Assign event_bus
        self.config = config       # Assign config
        
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
        # Normalize the symbol in the signal for consistent validation
        signal.symbol = normalize_symbol(signal.symbol)
        
        # For close signals, always validate them
        if signal.signal_type == 'close':
            return True, "Close signals are always valid"

        # Update our position tracker to get latest data
        self.position_tracker.update_positions()
        
        # If this is a buy signal, check if we already have a position for this symbol
        if signal.signal_type == 'buy':
            position = self.get_position(signal.symbol)
            if position and position.amount > 0:
                # Calculate position value
                position_value = position.amount * position.current_price
                if position_value > 1.0:  # Only consider positions worth more than $1
                    reason = f"Position already exists for {signal.symbol} (value: ${position_value:.2f})"
                    self.logger.warning(f"Signal rejected: {reason}")
                    return False, reason
        
        # Only count positions with value > $1 (PositionTracker.get_all_positions() now filters dust positions)
        current_positions = self.position_tracker.get_all_positions()
        self.logger.info(f"Current valid positions: {len(current_positions)}, max allowed: {self.max_open_trades}")

        # Check if we already have too many open trades
        if len(current_positions) >= self.max_open_trades:
            reason = f"Maximum number of open trades reached ({self.max_open_trades})"
            self.logger.warning(f"Signal rejected: {reason}")
            return False, reason
            
        # Note: We're no longer rejecting buy signals when the sell MAs are in a sell configuration.
        # This allows buy signals to be executed regardless of the sell MA configuration, with
        # the position being closed based on either the sell crossover or max drawdown.
        
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
            # Normalize the symbol in the signal
            signal.symbol = normalize_symbol(signal.symbol)
            
            # Update our position tracker to get latest data
            self.position_tracker.update_positions()
            
            # Get account balance
            balance = self.exchange.fetch_balance()
            
            # Get quote currency from the normalized symbol
            quote_currency = get_quote_currency(signal.symbol)
            available_balance = balance.get(quote_currency, {}).get('free', 0)
            
            if available_balance <= 0:
                self.logger.warning(f"No available balance in {quote_currency}")
                return 0
            
            # Count active positions to determine how many positions we already have
            # Only count positions with value > $1 (PositionTracker.get_all_positions() now filters dust positions)
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
            
            self.logger.info(f"Calculated position size: {position_size} {get_base_currency(signal.symbol)}")
            
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
        # Only check positions with value > $1 (PositionTracker.get_all_positions() now filters dust positions)
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
        # Normalize the symbol before querying position
        normalized_symbol = normalize_symbol(symbol)
        
        # Update positions before returning
        self.position_tracker.update_positions()
        return self.position_tracker.get_position(normalized_symbol)