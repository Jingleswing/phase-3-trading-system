# trading_bot/risk/basic_risk_manager.py
from typing import Dict, Tuple, Any, Optional, List
from trading_bot.interfaces.risk_manager import RiskManager
from trading_bot.models.data_models import Signal, Order, Position
from trading_bot.utils.logging import LoggerMixin

class BasicRiskManager(RiskManager, LoggerMixin):
    """
    Basic risk management implementation that uses equal division sizing
    based on total number of trading pairs.
    """
    
    def __init__(self, 
                 exchange,  # CCXT exchange instance
                 max_open_trades: int):  # Maximum number of open trades
        """
        Initialize the risk manager
        
        Args:
            exchange: CCXT exchange instance for account info
            max_open_trades: Maximum number of open trades (equal to total trading pairs)
        """
        self.exchange = exchange
        self.max_open_trades = max_open_trades
        self.logger.info(f"Initialized BasicRiskManager with max_open_trades={max_open_trades}")
    
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
        Calculate position size using available USDT balance divided by
        remaining positions (max_open_trades - current positions).
        
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
            
            # Count active positions to determine how many positions we already have
            active_positions = 0
            try:
                # Get positions for non-USDT coins (active spot positions)
                for currency, data in balance.items():
                    # Skip USDT and other quote currencies
                    if currency != quote_currency and isinstance(data, dict) and data.get('free', 0) > 0:
                        try:
                            # Check if this position is worth more than $1 (ignore dust)
                            currency_amount = float(data.get('free', 0))
                            # Try to get the USD value if possible
                            usd_value = 0
                            
                            # For simplicity, we'll try to get the symbol for this currency/USDT
                            symbol = f"{currency}/{quote_currency}"
                            try:
                                # Try to get the current market price
                                ticker = self.exchange.fetch_ticker(symbol)
                                last_price = float(ticker['last']) if 'last' in ticker and ticker['last'] else 0
                                usd_value = currency_amount * last_price
                            except Exception:
                                # If we can't get the price, estimate based on BTC or another method
                                # This is a fallback and may not be accurate for all coins
                                self.logger.debug(f"Couldn't get direct USD value for {currency}, using fallback")
                                usd_value = currency_amount  # Assume minimum 1:1 as fallback
                            
                            # Only count if worth more than $1
                            if usd_value > 1.0:
                                active_positions += 1
                                self.logger.debug(f"Counting {currency} position worth ${usd_value:.2f}")
                            else:
                                self.logger.debug(f"Ignoring dust {currency} position worth ${usd_value:.2f}")
                        except Exception as e:
                            self.logger.debug(f"Error calculating USD value for {currency}: {e}")
                            # If we can't determine value, assume it's a valid position
                            active_positions += 1
                
                # If the exchange supports fetch_positions, also count any futures positions
                if hasattr(self.exchange, 'fetch_positions'):
                    futures_positions = self.exchange.fetch_positions()
                    for position in futures_positions:
                        # Check if position has non-zero contracts and value > $1
                        contracts = float(position.get('contracts', 0))
                        notional = float(position.get('notional', 0))
                        
                        # If notional not available, try to calculate it
                        if notional == 0 and contracts > 0:
                            if 'markPrice' in position:
                                mark_price = float(position.get('markPrice', 0))
                                notional = contracts * mark_price
                                
                        # Only count significant positions (> $1)
                        if contracts > 0 and notional > 1.0:
                            active_positions += 1
                            self.logger.debug(f"Counting futures position worth ${notional:.2f}")
            except Exception as e:
                self.logger.error(f"Error counting active positions: {e}")
                # Use a fallback if we can't count positions
                active_positions = 0
            
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