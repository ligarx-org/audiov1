"""
Premium Management System
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class PremiumManager:
    """Premium mode management"""
    
    def __init__(self, db):
        self.db = db
        self._load_premium_status()
        logger.info(f"💎 Premium mode loaded: {'Enabled' if self.is_premium_enabled else 'Disabled'}")
    
    def _load_premium_status(self) -> None:
        """Load premium status from database"""
        try:
            status = self.db.get_bot_setting('premium_mode', 'disabled')
            self.is_premium_enabled = status == 'enabled'
        except Exception as e:
            logger.error(f"Error loading premium status: {e}")
            self.is_premium_enabled = False
    
    def is_premium_mode_enabled(self) -> bool:
        """Check if premium mode is enabled"""
        self._load_premium_status()  # Always get fresh status
        return self.is_premium_enabled
    
    def enable_premium_mode(self, admin_id: int) -> bool:
        """Enable premium mode"""
        try:
            if self.db.set_bot_setting('premium_mode', 'enabled'):
                self.is_premium_enabled = True
                logger.info(f"💎 Premium mode enabled by admin {admin_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error enabling premium: {e}")
            return False
    
    def disable_premium_mode(self, admin_id: int) -> bool:
        """Disable premium mode"""
        try:
            if self.db.set_bot_setting('premium_mode', 'disabled'):
                self.is_premium_enabled = False
                logger.info(f"💎 Premium mode disabled by admin {admin_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error disabling premium: {e}")
            return False
    
    def get_limit_text(self, user_lang: str = 'uz') -> str:
        """Get limit text based on premium status"""
        if self.is_premium_mode_enabled():
            return "💎 Premium: 2GB limit"
        else:
            return "⭐ Oddiy: 50MB limit"
