# trading_bot/execution/ccxt_executor.py
import ccxt
from typing import Dict, List, Any, Optional
from trading_bot.interfaces.order_executor import OrderExecutor
from trading_bot.models.data_models import Order, Trade, Position
from trading_bot.utils.logging import LoggerMixin

class CCXTExecutor(OrderExecutor, LoggerMixin):
    """
    Order executor using CCXT to place orders on exchanges
    """
    
    def __init__(self, exchange, dry_run: bool = True):
        """
        Initialize the order executor
        
        Args:
            exchange: CCXT exchange instance
            dry_run: If True, don't actually place orders
        """
        self.exchange = exchange
        self.dry_run = dry_run
        self.logger.info(f"Initialized CCXTExecutor (dry_run={dry_run})")
    
    def place_order(self, order: Order) -> Dict[str, Any]:
        """
        Place an order on the exchange
        
        Args:
            order: Order to place
            
        Returns:
            Order response from the exchange
        """
        # Log the order
        self.logger.info(f"Order: {order.side} {order.amount} {order.symbol} at {order.price or 'market price'}")
        
        # In dry run mode, just return a simulated response
        if self.dry_run:
            self.logger.info(f"DRY RUN: Order not actually placed")
            
            # Return a simulated order response
            from datetime import datetime
            import time
            import uuid
            
            timestamp = int(time.time() * 1000)
            order_id = str(uuid.uuid4())
            
            return {
                'id': order_id,
                'timestamp': timestamp,
                'datetime': datetime.fromtimestamp(timestamp / 1000).isoformat(),
                'symbol': order.symbol,
                'type': order.order_type,
                'side': order.side,
                'price': order.price,
                'amount': order.amount,
                'cost': order.price * order.amount if order.price else None,
                'status': 'open',
                'info': {'dry_run': True}
            }
        
        # Actually place the order
        try:
            # Prepare order parameters
            params = order.params or {}
            
            # Place the order based on order type
            if order.order_type == 'market':
                response = self.exchange.create_market_order(
                    symbol=order.symbol,
                    side=order.side,
                    amount=order.amount,
                    params=params
                )
            elif order.order_type == 'limit':
                response = self.exchange.create_limit_order(
                    symbol=order.symbol,
                    side=order.side,
                    amount=order.amount,
                    price=order.price,
                    params=params
                )
            else:
                raise ValueError(f"Unsupported order type: {order.order_type}")
            
            self.logger.info(f"Order placed successfully: {response['id']}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
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