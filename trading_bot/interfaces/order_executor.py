# trading_bot/interfaces/order_executor.py
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from trading_bot.models.data_models import Order, Trade, Position

class OrderExecutor(ABC):
    """
    Abstract interface for order execution.
    
    This interface defines methods for placing and managing orders on exchanges.
    """
    
    @abstractmethod
    def place_order(self, order: Order) -> Dict[str, Any]:
        """
        Place an order on the exchange
        
        Args:
            order: Order object with details
            
        Returns:
            Dictionary with order details from the exchange
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an existing order
        
        Args:
            order_id: ID of the order to cancel
            symbol: Symbol of the order
            
        Returns:
            True if cancelled successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders
        
        Args:
            symbol: Symbol to filter orders (optional)
            
        Returns:
            List of open orders
        """
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """
        Get current open positions
        
        Returns:
            List of Position objects
        """
        pass