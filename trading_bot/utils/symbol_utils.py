from typing import Optional

def normalize_symbol(symbol: str, default_quote: str = 'USDT') -> str:
    """
    Normalize trading symbol format to ensure consistency across the system.
    
    Different exchanges may return symbols in different formats:
    - 'BTC/USDT' (standard format)
    - 'BTCUSDT' (no separator)
    - 'BTC-USDT' (different separator)
    - 'BTC:USDT' (different separator for perpetual futures)
    
    This function standardizes all formats to 'BTC/USDT'.
    
    Args:
        symbol: Symbol string in any format
        default_quote: Default quote currency if none is specified
        
    Returns:
        Normalized symbol string in format 'BASE/QUOTE'
    """
    # Return empty string for None
    if symbol is None:
        return ""
    
    # Handle common separators
    if '/' in symbol:
        # Already in standard format
        return symbol
    elif ':' in symbol:
        # Handle perpetual futures format (e.g., 'BTC:USDT')
        # Extract the base and quote currencies
        parts = symbol.split(':')
        base = parts[0]
        quote = parts[1] if len(parts) > 1 else default_quote
        return f"{base}/{quote}"
    elif '-' in symbol:
        # Handle hyphen separator (e.g., 'BTC-USDT')
        parts = symbol.split('-')
        base = parts[0]
        quote = parts[1] if len(parts) > 1 else default_quote
        return f"{base}/{quote}"
    else:
        # No separator - try to identify base and quote
        # Common quote currencies
        quote_currencies = ['USDT', 'USD', 'BTC', 'ETH', 'BNB', 'BUSD', 'USDC']
        
        # Try to find a quote currency in the symbol
        for quote in quote_currencies:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                return f"{base}/{quote}"
        
        # If no quote currency found, assume default
        return f"{symbol}/{default_quote}"

def get_base_currency(symbol: str) -> str:
    """
    Extract base currency from a symbol
    
    Args:
        symbol: Trading pair symbol
        
    Returns:
        Base currency
    """
    normalized = normalize_symbol(symbol)
    return normalized.split('/')[0]

def get_quote_currency(symbol: str) -> str:
    """
    Extract quote currency from a symbol
    
    Args:
        symbol: Trading pair symbol
        
    Returns:
        Quote currency
    """
    normalized = normalize_symbol(symbol)
    parts = normalized.split('/')
    return parts[1] if len(parts) > 1 else 'USDT'

def is_same_symbol(symbol1: str, symbol2: str) -> bool:
    """
    Check if two symbols represent the same trading pair
    
    Args:
        symbol1: First symbol to compare
        symbol2: Second symbol to compare
        
    Returns:
        True if both symbols represent the same trading pair
    """
    return normalize_symbol(symbol1) == normalize_symbol(symbol2) 