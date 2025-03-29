# trading_bot/execution/ccxt_executor.py
import ccxt
from typing import Dict, List, Any, Optional
from trading_bot.interfaces.order_executor import OrderExecutor
from trading_bot.models.data_models import Order, Trade, Position
import logging
import time

class CCXTExecutor(OrderExecutor):
    """
    Order executor using CCXT to place orders on exchanges
    """
    
    def __init__(self, exchange, dry_run: bool = False):
        """
        Initialize the CCXT executor
        
        Args:
            exchange: CCXT exchange instance
            dry_run: Whether to run in dry run mode
        """
        self.exchange = exchange
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)
        self.orders_logger = logging.getLogger("orders")
        self.logger.info(f"Initialized CCXTExecutor (dry_run={dry_run})")
    
    def place_order(self, order: Order) -> Dict[str, Any]:
        """
        Place an order on the exchange
        
        Args:
            order: Order to place
            
        Returns:
            Order response from the exchange
        """
        return self.execute_order(order)
    
    def execute_order(self, order: Order) -> Dict:
        """
        Execute an order on the exchange
        
        Args:
            order: Order object with details
            
        Returns:
            Dictionary with order information
        """
        order_logger = logging.getLogger("orders")
        
        try:
            # Get trading pair
            symbol = order.symbol
            
            # Get order details
            order_type = order.order_type
            side = order.side
            amount = order.amount
            price = order.price
            
            # Log detailed order information
            self.logger.info(f"Order: {side} {amount} {symbol} at {order_type} price")
            order_logger.debug(
                f"Order details:\n"
                f"  Symbol: {symbol}\n"
                f"  Order Type: {order_type}\n"
                f"  Side: {side}\n"
                f"  Amount: {amount:.8f}\n"
                f"  Price: {price if price else 'Market'}"
            )
            
            # Conditionally log optional attributes if they exist
            order_id = getattr(order, 'id', None)
            if order_id is not None:
                order_logger.debug(f"  Order ID: {order_id}")
                
            strategy = getattr(order, 'strategy', None)
            if strategy is not None:
                order_logger.debug(f"  Strategy: {strategy}")
                
            signal_price = getattr(order, 'signal_price', None)
            if signal_price is not None:
                order_logger.debug(f"  Signal Price: {signal_price}")
            
            # Get market info to check limits
            markets = self.exchange.load_markets()
            if symbol in markets:
                market_info = markets[symbol]
                
                # Log market limits for debugging
                order_logger.debug(
                    f"Market info for {symbol}:\n"
                    f"  Limits - Amount: {market_info.get('limits', {}).get('amount', {})}\n"
                    f"  Limits - Price: {market_info.get('limits', {}).get('price', {})}\n"
                    f"  Limits - Cost: {market_info.get('limits', {}).get('cost', {})}\n"
                    f"  Precision - Amount: {market_info.get('precision', {}).get('amount')}\n"
                    f"  Precision - Price: {market_info.get('precision', {}).get('price')}"
                )
                
                # Check for minimum amount
                min_amount = market_info.get('limits', {}).get('amount', {}).get('min')
                if min_amount and amount < min_amount:
                    error_msg = f"{self.exchange.id} amount of {symbol} must be greater than minimum amount precision of {min_amount}"
                    self.logger.error(f"Error placing order: {error_msg}")
                    order_logger.error(f"Order validation failed: {error_msg}")
                    raise ValueError(error_msg)
                
                # Round amount to exchange precision if needed
                precision = market_info.get('precision', {}).get('amount')
                if precision is not None and isinstance(precision, int):
                    rounded_amount = round(amount, precision)
                    if rounded_amount != amount:
                        order_logger.debug(f"Amount adjusted for precision: {amount:.8f} -> {rounded_amount:.8f}")
                        amount = rounded_amount
            else:
                order_logger.warning(f"Could not find market info for {symbol}")
            
            # Set up parameters for the order
            params = {}
            
            # Need special handling for order types in some exchanges
            if order_type == 'market':
                # For market orders, don't include price
                order_result = self.exchange.create_order(
                    symbol=symbol,
                    type=order_type,
                    side=side,
                    amount=amount,
                    params=params
                )
            else:
                # For limit orders, include price
                if price is None:
                    error_msg = f"Price is required for limit orders"
                    self.logger.error(error_msg)
                    order_logger.error(error_msg)
                    raise ValueError(error_msg)
                
                order_result = self.exchange.create_order(
                    symbol=symbol,
                    type=order_type,
                    side=side,
                    amount=amount,
                    price=price,
                    params=params
                )
                
            # Log successful order
            self.logger.info(f"Order placed successfully: {order_result.get('id')}")
            order_logger.debug(f"Order response: {order_result}")
            
            return order_result
            
        except Exception as e:
            error_message = f"Error placing order: {str(e)}"
            self.logger.error(error_message)
            
            # Log detailed error information
            order_logger.error(
                f"Order execution error:\n"
                f"  Error: {str(e)}\n"
                f"  Error type: {type(e).__name__}\n"
                f"  Symbol: {order.symbol}\n"
                f"  Side: {order.side}\n"
                f"  Amount: {order.amount}\n"
                f"  Order type: {order.order_type}\n"
                f"  Exchange: {self.exchange.id}"
            )
            
            raise
    
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an existing order
        
        Args:
            order_id: ID of the order to cancel
            symbol: Symbol of the order
            
        Returns:
            True if cancelled successfully
        """
        # In dry run mode, just return True
        if self.dry_run:
            self.logger.info(f"DRY RUN: Cancelling order {order_id} (not actually cancelled)")
            return True
        
        try:
            response = self.exchange.cancel_order(order_id, symbol)
            self.logger.info(f"Order {order_id} cancelled successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders
        
        Args:
            symbol: Symbol to filter orders (optional)
            
        Returns:
            List of open orders
        """
        try:
            if symbol:
                orders = self.exchange.fetch_open_orders(symbol)
            else:
                # Some exchanges don't support fetching all open orders
                # In that case, this will fail and you'll need to fetch per symbol
                orders = self.exchange.fetch_open_orders()
                
            self.logger.debug(f"Retrieved {len(orders)} open orders")
            return orders
        except Exception as e:
            self.logger.error(f"Error retrieving open orders: {e}")
            if symbol is None:
                # Try to get all symbols and fetch orders for each
                try:
                    symbols = list(self.exchange.markets.keys())
                    all_orders = []
                    for sym in symbols:
                        try:
                            sym_orders = self.exchange.fetch_open_orders(sym)
                            all_orders.extend(sym_orders)
                        except:
                            pass
                    return all_orders
                except:
                    # If that fails too, just return empty list
                    return []
            raise
    
    def get_positions(self) -> List[Position]:
        """
        Get current open positions
        
        Returns:
            List of Position objects
        """
        try:
            # Some exchanges support direct position fetching
            if self.exchange.has['fetchPositions']:
                positions_data = self.exchange.fetch_positions()
                
                # Convert to Position objects
                positions = []
                for pos_data in positions_data:
                    if abs(float(pos_data['contracts'])) > 0:  # Only include non-zero positions
                        position = Position(
                            symbol=pos_data['symbol'],
                            side='long' if float(pos_data['contracts']) > 0 else 'short',
                            amount=abs(float(pos_data['contracts'])),
                            entry_price=float(pos_data['entryPrice']),
                            current_price=float(pos_data.get('markPrice', pos_data['entryPrice'])),
                            unrealized_pnl=float(pos_data.get('unrealizedPnl', 0))
                        )
                        positions.append(position)
                
                return positions
            else:
                # For exchanges without direct position fetching, we need to calculate from balances
                # This is simplified and won't work for all exchanges
                self.logger.warning("Exchange doesn't support direct position fetching. Using simplified approach.")
                balances = self.exchange.fetch_balance()
                positions = []
                
                for currency, data in balances.items():
                    if isinstance(data, dict) and data.get('total', 0) > 0:
                        # This is a very simplified approach
                        # In a real system you'd need to track entry prices separately
                        positions.append(Position(
                            symbol=f"{currency}/USDT",  # Simplified
                            side='long',  # Assuming all are long positions
                            amount=data.get('total', 0),
                            entry_price=0,  # Unknown
                            current_price=0  # Unknown
                        ))
                
                return positions
                
        except Exception as e:
            self.logger.error(f"Error retrieving positions: {e}")
            return []  # Return empty list on error