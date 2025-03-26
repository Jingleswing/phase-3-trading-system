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
                 max_open_trades: int = 3):  # Maximum number of open trades
        """
        Initialize the risk manager
        
        Args:
            exchange: CCXT exchange instance for account info
            risk_per_trade: Percentage of portfolio to risk per trade
            max_open_trades: Maximum number of open trades
        """
        self.exchange = exchange
        self.risk_per_trade = risk_per_trade
        self.max_open_trades = max_open_trades
        self.logger.info(f"Initialized BasicRiskManager (risk_per_trade={risk_per_trade}, max_open_trades={max_open_trades})")
    
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
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get current position for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Position object or None if no position exists
        """
        try:
            # For spot markets, check balance
            if ':USDT' not in symbol:  # Spot market
                base_currency = symbol.split('/')[0]
                balance = self.exchange.fetch_balance()
                if base_currency in balance and balance[base_currency]['free'] > 0:
                    return Position(
                        symbol=symbol,
                        side='long',  # Spot positions are always long
                        amount=float(balance[base_currency]['free']),
                        entry_price=0,  # We don't track entry price for spot
                        current_price=0  # We don't track current price for spot
                    )
            else:  # Futures market
                positions = self.exchange.fetch_positions([symbol])
                if positions and len(positions) > 0:
                    position_data = positions[0]
                    return Position(
                        symbol=symbol,
                        side='long' if position_data['side'] == 'long' else 'short',
                        amount=float(position_data['contracts']),
                        entry_price=float(position_data['entryPrice']),
                        current_price=float(position_data['markPrice']),
                        unrealized_pnl=float(position_data['unrealizedPnl'])
                    )
            return None
        except Exception as e:
            self.logger.error(f"Error fetching position for {symbol}: {e}")
            return None
    
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
            
            # Apply leverage for futures markets if specified
            market_type = signal.params.get('market_type', 'spot')
            if market_type == 'futures' and 'leverage' in signal.params:
                leverage = signal.params.get('leverage', 1)
                position_size = position_size * leverage
                self.logger.info(f"Applied {leverage}x leverage to position size")
            
            self.logger.info(f"Calculated position size: {position_size} {signal.symbol.split('/')[0]} "
                            f"(risking {amount_to_risk} {quote_currency}, {self.risk_per_trade*100}% of {available_balance})")
            
            return position_size
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0  # Return 0 on error to prevent trading
    
    def set_stop_loss(self, signal: Signal) -> Optional[Order]:
        """
        This method is required by the RiskManager interface but is not implemented
        as stop loss functionality has been disabled.
        
        Args:
            signal: Trading signal
            
        Returns:
            None as stop loss is disabled
        """
        return None