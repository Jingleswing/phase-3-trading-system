# trading_bot/strategies/factory.py
from typing import Dict, Any
from trading_bot.interfaces.strategy import Strategy
from trading_bot.utils.logging import LoggerMixin
from trading_bot.strategies.moving_average_crossover_spot import MovingAverageCrossoverSpot
from trading_bot.strategies.moving_average_crossover_futures import MovingAverageCrossoverFutures
from trading_bot.strategies.biased_spot_ma_crossover import BiasedSpotMACrossover

class StrategyFactory(LoggerMixin):
    """
    Factory class for creating strategy instances based on configuration
    """
    
    @staticmethod
    def create_strategy(config: Dict[str, Any], exchange=None) -> Strategy:
        """
        Create a strategy instance based on configuration
        
        Args:
            config: Strategy configuration dictionary
            exchange: Optional exchange instance to pass to the strategy
            
        Returns:
            Strategy instance
            
        Raises:
            ValueError: If strategy type is unknown or required parameters are missing
        """
        # Validate required config parameters
        if 'type' not in config:
            raise ValueError("Strategy configuration missing required parameter: 'type'")
            
        strategy_type = config['type']
        
        if 'params' not in config:
            raise ValueError("Strategy configuration missing required parameter: 'params'")
            
        params = config['params']
        
        # Get timeframe from config - require it explicitly as it should be provided
        if 'timeframe' not in config:
            raise ValueError("Strategy configuration missing required parameter: 'timeframe'")
            
        timeframe = config['timeframe']
        
        # Remove any position sizing parameters as they're now handled by risk manager
        params = {k: v for k, v in params.items() if k not in ['position_sizing', 'total_trading_pairs']}
        
        if strategy_type == 'moving_average_crossover_spot':
            # Extract required parameters that must be in config
            if 'short_period' not in params:
                raise ValueError("Missing required parameter 'short_period' for moving_average_crossover_spot strategy")
                
            if 'long_period' not in params:
                raise ValueError("Missing required parameter 'long_period' for moving_average_crossover_spot strategy")
                
            short_period = params['short_period']
            long_period = params['long_period']
            
            instance = MovingAverageCrossoverSpot(
                short_period=short_period,
                long_period=long_period
            )
            
            # Set the timeframe property on the strategy
            instance.timeframe = timeframe
            
            LoggerMixin().logger.info(f"Created {strategy_type} strategy with short_period={short_period}, long_period={long_period}, timeframe={timeframe}")
            return instance
            
        elif strategy_type == 'moving_average_crossover_futures':
            # Extract required parameters that must be in config
            required_params = ['short_period', 'long_period', 'leverage']
            for param in required_params:
                if param not in params:
                    raise ValueError(f"Missing required parameter '{param}' for moving_average_crossover_futures strategy")
                    
            short_period = params['short_period']
            long_period = params['long_period']
            leverage = params['leverage']
            
            instance = MovingAverageCrossoverFutures(
                short_period=short_period,
                long_period=long_period,
                leverage=leverage
            )
            
            # Set the timeframe property on the strategy
            instance.timeframe = timeframe
            
            LoggerMixin().logger.info(
                f"Created {strategy_type} strategy with short_period={short_period}, "
                f"long_period={long_period}, leverage={leverage}, timeframe={timeframe}"
            )
            return instance
            
        elif strategy_type == 'biased_spot_ma_crossover':
            # Extract required parameters that must be in config
            required_params = ['buy_short_period', 'buy_long_period', 'sell_short_period', 'sell_long_period']
            for param in required_params:
                if param not in params:
                    raise ValueError(f"Missing required parameter '{param}' for biased_spot_ma_crossover strategy")
                    
            buy_short_period = params['buy_short_period']
            buy_long_period = params['buy_long_period']
            sell_short_period = params['sell_short_period']
            sell_long_period = params['sell_long_period']
            
            instance = BiasedSpotMACrossover(
                buy_short_period=buy_short_period,
                buy_long_period=buy_long_period,
                sell_short_period=sell_short_period,
                sell_long_period=sell_long_period,
                exchange=exchange
            )
            
            # Set the timeframe property on the strategy
            instance.timeframe = timeframe
            
            LoggerMixin().logger.info(
                f"Created {strategy_type} strategy with "
                f"buy MA ({buy_short_period}/{buy_long_period}), "
                f"sell MA ({sell_short_period}/{sell_long_period}), "
                f"timeframe={timeframe}"
            )
            return instance
        
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}") 