# trading_bot/strategies/factory.py
from typing import Dict, Any
from trading_bot.interfaces.strategy import Strategy
from trading_bot.utils.logging import LoggerMixin
from trading_bot.strategies.moving_average import MovingAverageCrossover
from trading_bot.strategies.moving_average_crossover_spot import MovingAverageCrossoverSpot
from trading_bot.strategies.moving_average_crossover_futures import MovingAverageCrossoverFutures

class StrategyFactory(LoggerMixin):
    """
    Factory class for creating strategy instances based on configuration
    """
    
    @classmethod
    def create_strategy(cls, config: Dict[str, Any]) -> Strategy:
        """
        Create a strategy instance based on configuration
        
        Args:
            config: Strategy configuration dictionary
            
        Returns:
            Strategy instance
        """
        strategy_type = config.get('type')
        params = config.get('params', {})
        
        if strategy_type == 'moving_average_crossover_spot':
            # Extract parameters with defaults
            short_period = params.get('short_period', 20)
            long_period = params.get('long_period', 50)
            
            instance = MovingAverageCrossoverSpot(
                short_period=short_period,
                long_period=long_period
            )
            
            cls().logger.info(f"Created {strategy_type} strategy with short_period={short_period}, long_period={long_period}")
            return instance
            
        elif strategy_type == 'moving_average_crossover_futures':
            # Extract parameters with defaults
            short_period = params.get('short_period', 20)
            long_period = params.get('long_period', 50)
            leverage = params.get('leverage', 5)
            
            instance = MovingAverageCrossoverFutures(
                short_period=short_period,
                long_period=long_period,
                leverage=leverage
            )
            
            cls().logger.info(
                f"Created {strategy_type} strategy with short_period={short_period}, "
                f"long_period={long_period}, leverage={leverage}"
            )
            return instance
        
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}") 