#!/usr/bin/env python3
"""
Ultra-Fast Music Bot Runner
Supports 200+ concurrent users with error handling
Run this file to start the bot
"""

import sys
import os
import logging
import signal
import asyncio
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    """Setup logging configuration"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "bot.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\n🛑 Received signal {signum}. Shutting down gracefully...")
    sys.exit(0)

def main():
    """Main entry point"""
    print("🎵 Ultra-Fast Music Bot")
    print("=" * 50)
    print("🚀 Starting bot...")
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        from bot import main as bot_main
        bot_main()
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.error("💡 Make sure all dependencies are installed: pip3 install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error starting bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
