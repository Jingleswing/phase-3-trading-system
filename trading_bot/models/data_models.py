# trading_bot/models/data_models.py
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import pandas as pd
from trading_bot.utils.symbol_utils import normalize_symbol, get_base_currency, get_quote_currency
import json
import os
import uuid
import logging
from pathlib import Path

@dataclass
class Candle:
    """
    Represents OHLCV (Open, High, Low, Close, Volume) data for a time period
    """
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Candle':
        """Create a Candle instance from a dictionary"""
        return cls(
            timestamp=data['timestamp'] if isinstance(data['timestamp'], datetime) 
                     else pd.to_datetime(data['timestamp']),
            open=float(data['open']),
            high=float(data['high']),
            low=float(data['low']),
            close=float(data['close']),
            volume=float(data['volume']),
            symbol=data['symbol']
        )

@dataclass
class Trade:
    """
    Represents a completed trade
    """
    symbol: str
    order_id: str
    side: str  # 'buy' or 'sell'
    amount: float
    price: float
    cost: float
    fee: float
    timestamp: datetime
    
    @property
    def is_buy(self) -> bool:
        """Check if this is a buy trade"""
        return self.side.lower() == 'buy'
    
    @property
    def is_sell(self) -> bool:
        """Check if this is a sell trade"""
        return self.side.lower() == 'sell'

@dataclass
class Position:
    """
    Represents an open position
    """
    symbol: str
    side: str  # 'long' or 'short'
    amount: float
    entry_price: float
    current_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    entry_time: Optional[datetime] = None
    max_price: float = 0.0
    min_price: float = 0.0
    
    def __post_init__(self):
        """Initialize max and min prices if not set"""
        if self.max_price == 0.0:
            self.max_price = self.current_price
        if self.min_price == 0.0:
            self.min_price = self.current_price
        if self.entry_time is None:
            self.entry_time = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Position to a dictionary for serialization"""
        data = asdict(self)
        # Convert datetime to string for JSON serialization
        if data['entry_time']:
            data['entry_time'] = data['entry_time'].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Position':
        """Create a Position instance from a dictionary"""
        # Convert string back to datetime
        if 'entry_time' in data and isinstance(data['entry_time'], str):
            try:
                data['entry_time'] = datetime.fromisoformat(data['entry_time'])
            except ValueError:
                data['entry_time'] = datetime.now()
        
        return cls(**data)
    
    def update_price(self, price: float) -> None:
        """
        Update the current price and unrealized PnL
        Also track max and min prices for drawdown calculation
        """
        self.current_price = price
        
        # Update max and min prices
        if price > self.max_price:
            self.max_price = price
        if price < self.min_price or self.min_price == 0:
            self.min_price = price
            
        # Calculate unrealized PnL
        if self.side.lower() == 'long':
            self.unrealized_pnl = (self.current_price - self.entry_price) * self.amount
        else:
            self.unrealized_pnl = (self.entry_price - self.current_price) * self.amount
    
    @property
    def current_drawdown_percentage(self) -> float:
        """
        Calculate current drawdown as a percentage from the highest point
        For long positions, drawdown is (max_price - current_price) / max_price
        For short positions, drawdown is (current_price - min_price) / min_price
        
        Returns:
            Drawdown as a decimal (0.1 = 10% drawdown)
        """
        if self.side.lower() == 'long':
            # For long positions, we care about drawdown from the highest price
            if self.max_price <= 0:
                return 0.0
            return (self.max_price - self.current_price) / self.max_price
        else:
            # For short positions, we care about drawdown from the lowest price
            if self.min_price <= 0:
                return 0.0
            return (self.current_price - self.min_price) / self.min_price
    
    @property
    def profit_percentage(self) -> float:
        """
        Calculate current profit as a percentage of entry price
        
        Returns:
            Profit percentage as a decimal (0.1 = 10% profit)
        """
        if self.entry_price <= 0:
            return 0.0
            
        if self.side.lower() == 'long':
            return (self.current_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - self.current_price) / self.entry_price
    
    @property
    def duration(self) -> timedelta:
        """
        Calculate how long the position has been open
        
        Returns:
            Time duration since position entry
        """
        if self.entry_time is None:
            return timedelta(0)
        return datetime.now() - self.entry_time

@dataclass
class Signal:
    """
    Trading signal generated by a strategy
    """
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'close'
    price: float
    strategy_name: str
    params: Dict[str, Any] = None
    strength: float = 1.0  # Signal strength/confidence (0.0 to 1.0)
    
    def __post_init__(self):
        if self.params is None:
            self.params = {}

@dataclass
class Order:
    """
    Order to be executed on an exchange
    """
    symbol: str
    order_type: str  # 'market', 'limit', etc.
    side: str  # 'buy' or 'sell'
    amount: float
    price: Optional[float] = None  # Required for limit orders
    params: Dict[str, Any] = None
    id: Optional[str] = None  # Order ID (typically assigned by exchange after execution)
    strategy: Optional[str] = None  # Name of the strategy that generated this order
    signal_price: Optional[float] = None  # Price at which the signal was generated
    
    def __post_init__(self):
        if self.params is None:
            self.params = {}
        
        # For market orders, price can be None
        if self.order_type.lower() == 'market':
            self.price = None
        # For limit orders, price is required
        elif self.price is None and self.order_type.lower() == 'limit':
            raise ValueError("Price is required for limit orders")

class PositionTracker:
    """
    Tracks the state of open positions including entry price, current price,
    and drawdown metrics to enable risk management based on position performance.
    """
    
    def __init__(self, exchange):
        """
        Initialize the position tracker
        
        Args:
            exchange: CCXT exchange instance used to fetch current positions
        """
        self.exchange = exchange
        self._positions: Dict[str, Position] = {}  # Symbol -> Position
        self._closed_positions: List[Position] = []  # History of closed positions
        self._last_update: Optional[datetime] = None  # Track last position update
        self._update_interval = timedelta(seconds=5)  # Minimum time between updates
        
        # Set default data directory
        self.data_dir = Path("logs")
        self.data_dir.mkdir(exist_ok=True)
        self.position_file = self.data_dir / "positions.json"
        
        # Load persisted positions on startup
        self._load_positions()
    
    def _should_update(self) -> bool:
        """
        Check if positions should be updated based on time interval
        
        Returns:
            bool: True if positions should be updated
        """
        if self._last_update is None:
            return True
        return datetime.now() - self._last_update > self._update_interval
    
    def _load_positions(self) -> None:
        """Load position data from disk"""
        if not self.position_file.exists():
            logging.getLogger(__name__).info("No saved position data found")
            return
            
        try:
            with open(self.position_file, 'r') as f:
                data = json.load(f)
                
            # Load open positions
            if 'positions' in data:
                for pos_data in data['positions']:
                    try:
                        position = Position.from_dict(pos_data)
                        self._positions[position.symbol] = position
                        logging.getLogger(__name__).info(
                            f"Loaded position: {position.symbol}, entry_price: {position.entry_price}, "
                            f"max_price: {position.max_price}, min_price: {position.min_price}"
                        )
                    except Exception as e:
                        logging.getLogger(__name__).error(f"Error loading position: {e}")
            
            # Load closed positions history (limited to last 100)
            if 'closed_positions' in data:
                for pos_data in data['closed_positions'][-100:]:
                    try:
                        position = Position.from_dict(pos_data)
                        self._closed_positions.append(position)
                    except Exception as e:
                        logging.getLogger(__name__).error(f"Error loading closed position: {e}")
                        
            logging.getLogger(__name__).info(
                f"Loaded {len(self._positions)} positions and {len(self._closed_positions)} closed positions"
            )
                
        except Exception as e:
            logging.getLogger(__name__).error(f"Error loading positions from file: {e}")
    
    def _save_positions(self) -> None:
        """Save position data to disk"""
        try:
            data = {
                'positions': [p.to_dict() for p in self._positions.values()],
                'closed_positions': [p.to_dict() for p in self._closed_positions[-100:]]  # Save last 100 only
            }
            
            with open(self.position_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logging.getLogger(__name__).debug("Saved positions to disk")
                
        except Exception as e:
            logging.getLogger(__name__).error(f"Error saving positions to file: {e}")
    
    def _get_entry_price_from_trades(self, symbol: str, amount: float) -> float:
        """
        Attempt to calculate average entry price from recent trades
        
        Args:
            symbol: Trading pair symbol
            amount: Current position amount
            
        Returns:
            Average entry price or 0 if trades can't be retrieved
        """
        try:
            # Try to fetch recent trades for this symbol
            trades = self.exchange.fetch_my_trades(symbol, limit=20)
            
            if not trades:
                return 0
            
            # Sort by timestamp (oldest first)
            trades.sort(key=lambda x: x['timestamp'])
            
            # Calculate weighted average entry price
            total_cost = 0
            total_amount = 0
            
            # Process trades until we reach approximately current position size
            for trade in reversed(trades):  # Start with most recent trades
                if trade['side'].lower() != 'buy':
                    continue
                    
                trade_amount = float(trade['amount'])
                trade_price = float(trade['price'])
                
                total_cost += trade_amount * trade_price
                total_amount += trade_amount
                
                # Break if we've accumulated enough to explain current position
                if total_amount >= amount * 0.9:  # Allow for small differences
                    break
            
            # Calculate average entry price if we found relevant trades
            if total_amount > 0:
                return total_cost / total_amount
                
            return 0
            
        except Exception as e:
            logging.getLogger(__name__).debug(f"Error getting trade history for {symbol}: {e}")
            return 0
    
    def update_positions(self) -> None:
        """
        Update position information from the exchange
        
        This should be called regularly to keep position data current.
        Updates are rate-limited to avoid excessive API calls.
        """
        if not self._should_update():
            return
            
        try:
            # Store existing position data to preserve tracking info
            existing_positions = {symbol: pos for symbol, pos in self._positions.items()}
            
            # Clear current positions but keep closed positions history
            self._positions = {}
            
            # Get exchange positions (for futures)
            exchange_positions = []
            if hasattr(self.exchange, 'fetch_positions'):
                try:
                    exchange_positions = self.exchange.fetch_positions()
                    for pos_data in exchange_positions:
                        # Skip if pos_data is not a dictionary
                        if not isinstance(pos_data, dict):
                            continue
                            
                        # Normalize the symbol format
                        symbol = normalize_symbol(pos_data.get('symbol', ''))
                        
                        # Safely convert contracts to float or use 0 if not present or not convertible
                        contracts = 0
                        try:
                            contracts_value = pos_data.get('contracts', 0)
                            contracts = float(contracts_value) if contracts_value is not None else 0
                        except (ValueError, TypeError):
                            continue  # Skip if can't convert to float
                        
                        # Only process if position size > 0
                        if contracts > 0:
                            # Safely extract and convert other values
                            try:
                                entry_price = float(pos_data.get('entryPrice', 0) or 0)
                                mark_price = float(pos_data.get('markPrice', 0) or 0)
                                side = str(pos_data.get('side', 'long')).lower()
                                unrealized_pnl = float(pos_data.get('unrealizedPnl', 0) or 0)
                                
                                # Update existing position or create new one
                                normalized_symbol = normalize_symbol(symbol)
                                if normalized_symbol in existing_positions:
                                    # Update existing position with new price but keep tracking info
                                    position = existing_positions[normalized_symbol]
                                    position.update_price(mark_price)
                                    position.amount = contracts  # Update amount in case it changed
                                    position.unrealized_pnl = unrealized_pnl
                                    self._positions[normalized_symbol] = position
                                else:
                                    # Create new position
                                    self._positions[normalized_symbol] = Position(
                                        symbol=normalized_symbol,
                                        side=side,
                                        amount=contracts,
                                        entry_price=entry_price,
                                        current_price=mark_price,
                                        unrealized_pnl=unrealized_pnl,
                                        entry_time=datetime.now()
                                    )
                            except (ValueError, TypeError) as e:
                                logging.getLogger(__name__).debug(f"Error processing position data for {symbol}: {e}")
                                continue
                except Exception as e:
                    logging.getLogger(__name__).error(f"Error fetching positions: {e}")
            
            # Get spot balances (for spot positions)
            balance = {}
            try:
                balance = self.exchange.fetch_balance()
            except Exception as e:
                logging.getLogger(__name__).error(f"Error fetching balance: {e}")
                balance = {}
            
            # Process non-quote currency balances (spot positions)
            for currency, data in balance.items():
                # Skip checking quote currencies like USDT
                if currency in ['USDT', 'USD', 'BUSD', 'USDC']:
                    continue
                
                # Skip if data is not a dictionary
                if not isinstance(data, dict):
                    continue
                    
                # Safely extract free amount
                free_amount = 0
                try:
                    free_value = data.get('free', 0)
                    free_amount = float(free_value) if free_value is not None else 0
                except (ValueError, TypeError):
                    continue
                
                # Only process if balance > 0
                if free_amount > 0:
                    # Try to get current price for this asset
                    symbol = f"{currency}/USDT"  # Standardized format
                    try:
                        # Use the original format for fetching price from exchange
                        ticker = self.exchange.fetch_ticker(symbol)
                        if not isinstance(ticker, dict):
                            continue
                            
                        current_price = 0
                        try:
                            price_value = ticker.get('last', 0)
                            current_price = float(price_value) if price_value is not None else 0
                        except (ValueError, TypeError):
                            continue
                        
                        # Only process if we can get a price
                        if current_price > 0:
                            # Update existing position or create new one
                            normalized_symbol = normalize_symbol(symbol)
                            if normalized_symbol in existing_positions:
                                # Update existing position with new price but keep tracking info
                                position = existing_positions[normalized_symbol]
                                position.update_price(current_price)
                                position.amount = free_amount  # Update amount in case it changed
                                self._positions[normalized_symbol] = position
                            else:
                                # Try to get a better entry price from trade history
                                entry_price = self._get_entry_price_from_trades(symbol, free_amount)
                                
                                # Fall back to current price if we couldn't get entry price from trades
                                if entry_price <= 0:
                                    entry_price = current_price
                                
                                # Create new position with the best entry price we could find
                                self._positions[normalized_symbol] = Position(
                                    symbol=normalized_symbol,
                                    side='long',  # Spot positions are always long
                                    amount=free_amount,
                                    entry_price=entry_price,
                                    current_price=current_price,
                                    entry_time=datetime.now()
                                )
                    except Exception as e:
                        logging.getLogger(__name__).debug(f"Error getting price for {symbol}: {e}")
                        # Skip if we can't get price info
                        pass
            
            # Check for positions that no longer exist on the exchange
            for symbol, position in list(existing_positions.items()):
                if symbol not in self._positions:
                    # Position no longer exists - add to closed positions
                    self._closed_positions.append(position)
                    logging.getLogger(__name__).info(f"Position {symbol} closed (no longer on exchange)")
                
            # Save updated positions to disk
            self._save_positions()
            
            # Update last update timestamp
            self._last_update = datetime.now()
                
        except Exception as e:
            logging.getLogger(__name__).error(f"Error updating positions: {e}")
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position information for a specific symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Position object or None if no position exists
        """
        # Normalize the input symbol before lookup
        normalized_symbol = normalize_symbol(symbol)
        position = self._positions.get(normalized_symbol)
        
        # If no position was found in our tracker, try to directly fetch from exchange
        # This is especially important for spot positions that might not be properly tracked
        if position is None and self._should_update():
            try:
                # For spot positions, check if we have a balance
                base_currency = get_base_currency(normalized_symbol)
                if not base_currency:
                    return None
                    
                try:
                    balance = self.exchange.fetch_balance()
                    if base_currency in balance:
                        free_amount = float(balance[base_currency].get('free', 0) or 0)
                        if free_amount > 0:
                            # We have a balance - check current price
                            ticker = self.exchange.fetch_ticker(normalized_symbol)
                            if isinstance(ticker, dict) and 'last' in ticker:
                                current_price = float(ticker['last'])
                                
                                # Create a position object on-the-fly
                                position = Position(
                                    symbol=normalized_symbol,
                                    side='long',  # Spot positions are always long
                                    amount=free_amount,
                                    entry_price=current_price,  # Approximation
                                    current_price=current_price,
                                    entry_time=datetime.now()
                                )
                                
                                # Save this in our tracker
                                self._positions[normalized_symbol] = position
                                return position
                except Exception as e:
                    logging.getLogger(__name__).error(f"Error directly checking position for {normalized_symbol}: {e}")
            except Exception as e:
                logging.getLogger(__name__).error(f"Error fetching position for {normalized_symbol}: {e}")
        
        return position
    
    def get_all_positions(self) -> List[Position]:
        """
        Get all current positions with a value greater than $1
        Positions with value less than $1 are considered dust and ignored
        
        Returns:
            List of Position objects with value > $1
        """
        # Filter out positions with value less than $1
        valid_positions = []
        for position in self._positions.values():
            position_value = position.amount * position.current_price
            if position_value > 1.0:
                valid_positions.append(position)
            else:
                logging.getLogger(__name__).debug(
                    f"Ignoring dust position for {position.symbol}: "
                    f"{position.amount} units at {position.current_price}, "
                    f"value=${position_value:.2f}"
                )
        
        return valid_positions
    
    def get_closed_positions(self) -> List[Position]:
        """
        Get history of closed positions
        
        Returns:
            List of closed Position objects
        """
        return self._closed_positions
    
    def record_position(self, symbol: str, side: str, amount: float, 
                       entry_price: float, current_price: float) -> None:
        """
        Manually record a new position
        
        Args:
            symbol: Trading pair symbol
            side: 'long' or 'short'
            amount: Position size
            entry_price: Entry price
            current_price: Current price
        """
        # Normalize the symbol before storing
        normalized_symbol = normalize_symbol(symbol)
        self._positions[normalized_symbol] = Position(
            symbol=normalized_symbol,
            side=side,
            amount=amount,
            entry_price=entry_price,
            current_price=current_price,
            entry_time=datetime.now()
        )
        
        # Save after recording a new position
        self._save_positions()
    
    def close_position(self, symbol: str) -> None:
        """
        Mark a position as closed and move it to closed_positions
        
        Args:
            symbol: Trading pair symbol
        """
        # Normalize the symbol before lookup
        normalized_symbol = normalize_symbol(symbol)
        if normalized_symbol in self._positions:
            # Add to closed positions history
            self._closed_positions.append(self._positions[normalized_symbol])
            # Remove from active positions
            del self._positions[normalized_symbol]
            
            # Save after closing a position
            self._save_positions()