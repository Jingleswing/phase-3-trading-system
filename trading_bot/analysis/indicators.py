# trading_bot/analysis/indicators.py
import pandas as pd
import numpy as np
from typing import Optional

def sma(data: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
    """
    Calculate Simple Moving Average
    
    Args:
        data: DataFrame with price data
        period: SMA period
        column: Column to use for calculation
        
    Returns:
        Series with SMA values
    """
    return data[column].rolling(window=period).mean()

def ema(data: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
    """
    Calculate Exponential Moving Average
    
    Args:
        data: DataFrame with price data
        period: EMA period
        column: Column to use for calculation
        
    Returns:
        Series with EMA values
    """
    return data[column].ewm(span=period, adjust=False).mean()

def calculate_indicators(data: pd.DataFrame, indicators_config: list) -> pd.DataFrame:
    """
    Calculate multiple indicators based on configuration
    
    Args:
        data: DataFrame with price data
        indicators_config: List of indicator configurations
        
    Returns:
        DataFrame with added indicators
    """
    df = data.copy()
    
    # Map of indicator names to functions
    indicator_functions = {
        'sma': sma,
        'ema': ema,
    }
    
    # Calculate each indicator
    for config in indicators_config:
        name = config['name']
        params = config.get('params', {})
        output_column = config.get('output_column')
        
        if name in indicator_functions:
            if output_column is None:
                # Use default name if output_column not specified
                output_column = f"{name}_{params.get('period')}"
                
            # Calculate the indicator
            df[output_column] = indicator_functions[name](df, **params)
        else:
            raise ValueError(f"Unknown indicator: {name}")
    
    return df