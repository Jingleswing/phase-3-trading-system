# trading_bot/utils/events.py
from enum import Enum, auto
from typing import Dict, List, Callable, Any
from dataclasses import dataclass
import time
import logging

# Configure logging
logger = logging.getLogger(__name__)

class EventType(Enum):
    """Types of events that can be emitted in the trading system"""
    # Market data events
    PRICE_UPDATE = auto()
    NEW_CANDLE = auto()
    ORDERBOOK_UPDATE = auto()
    
    # Trading signal events
    SIGNAL_GENERATED = auto()
    
    # Order events
    ORDER_PLACED = auto()
    ORDER_FILLED = auto()
    ORDER_CANCELLED = auto()
    ORDER_REJECTED = auto()
    
    # System events
    STARTUP = auto()
    SHUTDOWN = auto()
    ERROR = auto()

@dataclass
class Event:
    """Event object containing type and data"""
    type: EventType
    data: Dict[str, Any]
    timestamp: float = None
    
    def __post_init__(self):
        # Set timestamp if not provided
        if self.timestamp is None:
            self.timestamp = time.time()

class EventBus:
    """
    Simple event bus for pub/sub pattern.
    
    This class allows components to subscribe to specific event types
    and publish events to be processed by all subscribers.
    """
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        
    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """
        Subscribe to an event type with a callback function
        
        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event is published
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to {event_type.name}")
        
    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """
        Unsubscribe from an event type
        
        Args:
            event_type: Type of event to unsubscribe from
            callback: Callback function to remove
        """
        if event_type in self._subscribers and callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)
            logger.debug(f"Unsubscribed from {event_type.name}")
        
    def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers
        
        Args:
            event: Event object to publish
        """
        if event.type in self._subscribers:
            for callback in self._subscribers[event.type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Error in event handler for {event.type.name}: {e}")
                    
            logger.debug(f"Published {event.type.name} event to {len(self._subscribers[event.type])} subscribers")