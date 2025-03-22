# trading_bot/risk/basic_risk_manager.py
from typing import Dict, Tuple, Any, Optional, List
from trading_bot.interfaces.risk_manager import RiskManager
from trading_bot.models.data_models import Signal, Order, Position
from trading_bot.utils.logging import LoggerMixin

class BasicRiskManager(RiskManager, LoggerMixin):
    """
    Basic risk management implementation
    """
    
    def __init__(self, 
                 exchange,  # CCXT exchange instance
                 risk_per_trade: float = 0.02,  # 2% of portfolio per trade
                 max_open_trades: int = 3,
                 stop_loss_pct: float = 0.05):  # 5% stop loss
        """
        Initialize the risk manager
        
        Args:
            exchange: CCXT exchange instance for account info
            risk_per_trade: Percentage of portfolio to risk per trade
            max_open_trades: Maximum number of open trades
            stop_loss_pct: Stop loss percentage
        """
        self.exchange = exchange
        self.risk_per_trade = risk_per_trade
        self.max_open_trades = max_open_trades
        self.stop_loss_pct = stop_loss_pct
        self.logger.info(f"Initialized BasicRiskManager (risk_per_trade={risk_per_trade}, max_open_trades={max_open_trades})")
    
    def validate_signal(self, signal: Signal) -> Tuple[bool, str]:
        """
        Validate if a signal should be executed based on risk rules
        
        Args:
            signal: Signal to validate
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check if we already have too many open trades
        try:
            # Get positions through the exchange
            if hasattr(self.exchange, 'fetch_positions'):
                positions = self.exchange.fetch_positions()
                open_positions = [p for p in positions if abs(float(p['contracts'])) > 0]
                
                if len(open_positions) >= self.max_open_trades:
                    reason = f"Maximum number of open trades reached ({self.max_open_trades})"
                    self.logger.warning(f"Signal rejected: {reason}")
                    return False, reason
            else:
                # If we can't directly fetch positions, skip this check
                self.logger.warning("Cannot verify number of open trades - exchange doesn't support fetch_positions")
        except Exception as e:
            self.logger.error(f"Error checking open positions: {e}")
            # Continue anyway, don't block the signal
        
        # TODO: Add more validation rules as needed
        # e.g., check if we have enough balance, check market conditions, etc.
        
        return True, "Signal validated"
    
    def calculate_position_size(self, signal: Signal) -> float:
        """
        Calculate appropriate position size for a signal
        
        Args:
            signal: Trading signal
            
        Returns:
            Position size in base currency
        """
        try:
            # Get account balance
            balance = self.exchange.fetch_balance()
            
            # For simplicity, assuming we're trading against USDT
            quote_currency = signal.symbol.split('/')[1]  # e.g., 'USDT' from 'ETH/USDT'
            available_balance = balance.get(quote_currency, {}).get('free', 0)
            
            if available_balance <= 0:
                self.logger.warning(f"No available balance in {quote_currency}")
                return 0
            
            # Calculate amount to risk
            amount_to_risk = available_balance * self.risk_per_trade
            
            # Calculate position size based on price
            position_size = amount_to_risk / signal.price
            
            self.logger.info(f"Calculated position size: {position_size} {signal.symbol.split('/')[0]} "
                            f"(risking {amount_to_risk} {quote_currency}, {self.risk_per_trade*100}% of {available_balance})")
            
            return position_size
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0  # Return 0 on error to prevent trading
    
    def set_stop_loss(self, signal: Signal) -> Optional[Order]:
        """
        Create a stop loss order for a signal
        
        Args:
            signal: Trading signal
            
        Returns:
            Stop loss order or None if not applicable
        """
        if signal.signal_type != 'buy':
            # Only set stop loss for buy signals
            return None
        
        # Calculate stop loss price
        stop_price = signal.price * (1 - self.stop_loss_pct)
        
        # Create stop loss order
        stop_loss_order = Order(
            symbol=signal.symbol,
            order_type='stop',  # This may need to be adjusted based on the exchange
            side='sell',
            amount=0,  # Will be filled in later
            price=stop_price,
            params={
                'stopPrice': stop_price,
                'reduceOnly': True
            }
        )
        
        self.logger.info(f"Created stop loss order at {stop_price} ({self.stop_loss_pct*100}% below entry)")
        return stop_loss_order