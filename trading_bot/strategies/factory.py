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
    def create_strategy(config: Dict[str, Any]) -> Strategy:
        """
        Create a strategy instance based on configuration
        
        Args:
            config: Strategy configuration dictionary
            
        Returns:
            Strategy instance
            
        Raises:
            ValueError: If strategy type is unknown or required parameters are missing
        """
        strategy_type = config.get('type')
        params = config.get('params', {})
        
        # Remove any position sizing parameters as they're now handled by risk manager
        params = {k: v for k, v in params.items() if k not in ['position_sizing', 'total_trading_pairs']}
        
        if strategy_type == 'moving_average_crossover_spot':
            # Extract required parameters
            short_period = params.get('short_period')
            long_period = params.get('long_period')
            
            if short_period is None or long_period is None:
                raise ValueError("Missing required parameters for moving_average_crossover_spot strategy")
            
            instance = MovingAverageCrossoverSpot(
                short_period=short_period,
                long_period=long_period
            )
            
            LoggerMixin().logger.info(f"Created {strategy_type} strategy with short_period={short_period}, long_period={long_period}")
            return instance
            
        elif strategy_type == 'moving_average_crossover_futures':
            # Extract required parameters
            short_period = params.get('short_period')
            long_period = params.get('long_period')
            leverage = params.get('leverage')
            
            if short_period is None or long_period is None or leverage is None:
                raise ValueError("Missing required parameters for moving_average_crossover_futures strategy")
            
            instance = MovingAverageCrossoverFutures(
                short_period=short_period,
                long_period=long_period,
                leverage=leverage
            )
            
            LoggerMixin().logger.info(
                f"Created {strategy_type} strategy with short_period={short_period}, "
                f"long_period={long_period}, leverage={leverage}"
            )
            return instance
            
        elif strategy_type == 'biased_spot_ma_crossover':
            # Extract required parameters
            buy_short_period = params.get('buy_short_period')
            buy_long_period = params.get('buy_long_period')
            sell_short_period = params.get('sell_short_period')
            sell_long_period = params.get('sell_long_period')
            
            if any(param is None for param in [buy_short_period, buy_long_period, 
                                             sell_short_period, sell_long_period]):
                raise ValueError("Missing required parameters for biased_spot_ma_crossover strategy")
            
            instance = BiasedSpotMACrossover(
                buy_short_period=buy_short_period,
                buy_long_period=buy_long_period,
                sell_short_period=sell_short_period,
                sell_long_period=sell_long_period
            )
            
            LoggerMixin().logger.info(
                f"Created {strategy_type} strategy with "
                f"buy MA ({buy_short_period}/{buy_long_period}), "
                f"sell MA ({sell_short_period}/{sell_long_period})"
            )
            return instance
        
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}") 