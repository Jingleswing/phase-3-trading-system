# trading_bot/analysis/indicators.py
import pandas as pd
import numpy as np
import logging
from typing import Optional, Dict, Any, List

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
    logger = logging.getLogger("indicators")
    logger.debug(f"Calculating SMA with period={period} on column='{column}', data shape: {data.shape}")
    
    result = data[column].rolling(window=period).mean()
    
    # Log diagnostic info
    null_count = result.isnull().sum()
    logger.debug(f"SMA period={period} results: {null_count} NaN values ({null_count/len(result)*100:.2f}%), " 
                f"range: {result.min():.6f} - {result.max():.6f}")
    
    return result

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
    logger = logging.getLogger("indicators")
    logger.debug(f"Calculating EMA with period={period} on column='{column}', data shape: {data.shape}")
    
    result = data[column].ewm(span=period, adjust=False).mean()
    
    # Log diagnostic info
    null_count = result.isnull().sum()
    logger.debug(f"EMA period={period} results: {null_count} NaN values ({null_count/len(result)*100:.2f}%), " 
                f"range: {result.min():.6f} - {result.max():.6f}")
    
    return result

def calculate_indicators(data: pd.DataFrame, indicators_config: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Calculate multiple indicators based on configuration
    
    Args:
        data: DataFrame with price data
        indicators_config: List of indicator configurations
        
    Returns:
        DataFrame with added indicators
    """
    df = data.copy()
    logger = logging.getLogger("indicators")
    
    logger.debug(f"Calculating indicators with input data shape: {data.shape}")
    logger.debug(f"Input columns: {data.columns.tolist()}")
    logger.debug(f"Indicator configurations: {indicators_config}")
    
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
        
        logger.debug(f"Calculating {name} with params: {params}")
        
        if name in indicator_functions:
            if output_column is None:
                # Use default name if output_column not specified
                output_column = f"{name}_{params.get('period')}"
                
            # Calculate the indicator
            df[output_column] = indicator_functions[name](df, **params)
            
            # Log sample results
            logger.debug(f"{name} calculation for {output_column} completed.")
            if len(df) > 3:
                sample = df[[output_column]].tail(3)
                logger.debug(f"Sample values (last 3 rows):\n{sample.to_dict('records')}")
        else:
            error_msg = f"Unknown indicator: {name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    logger.debug(f"Indicators calculation complete. Output columns: {df.columns.tolist()}")
    return df