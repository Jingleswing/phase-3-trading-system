#!/usr/bin/env python
# debug_bot.py - Run the trading bot with enhanced logging
import argparse
import sys
import os
import logging
import time
import threading
from pathlib import Path

# Add the project root to the path so we can import our modules
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from trading_bot.main import TradingBot

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Run trading bot with enhanced logging')
    parser.add_argument('-c', '--config', type=str, required=True,
                       help='Path to configuration file')
    parser.add_argument('-t', '--runtime', type=int, default=300,
                       help='How long to run the bot before stopping (seconds)')
    return parser.parse_args()

def setup_debug_environment():
    """Set up environment for debugging"""
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(PROJECT_ROOT, 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
        
    # Set up basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(logs_dir, 'debug_bot.log'))
        ]
    )

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_args()
    
    # Set up environment
    setup_debug_environment()
    
    # Check if config file exists
    config_path = args.config
    if not os.path.exists(config_path):
        logging.error(f"Config file not found: {config_path}")
        return
    
    # Run the bot
    try:
        logging.info(f"Starting trading bot with config: {config_path}")
        logging.info(f"Will run for {args.runtime} seconds before stopping")
        
        # Create the bot
        bot = TradingBot(config_path)
        
        # Start the bot in a separate thread
        bot.running = True
        bot_thread = threading.Thread(target=bot.run)
        bot_thread.daemon = True
        bot_thread.start()
        
        # Run for specified time
        time.sleep(args.runtime)
        
        # Gracefully stop the bot
        logging.info("Stopping trading bot")
        bot.running = False
        bot_thread.join(timeout=10)  # Wait up to 10 seconds for the thread to finish
        
        logging.info("Debug session complete. Check logs directory for results.")
        
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
        if 'bot' in locals() and hasattr(bot, 'running'):
            bot.running = False
            if 'bot_thread' in locals() and bot_thread.is_alive():
                bot_thread.join(timeout=5)
        
    except Exception as e:
        logging.error(f"Error running bot: {str(e)}", exc_info=True)
        if 'bot' in locals() and hasattr(bot, 'running'):
            bot.running = False
            if 'bot_thread' in locals() and bot_thread.is_alive():
                bot_thread.join(timeout=5)

if __name__ == "__main__":
    main() 