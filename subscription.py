"""
3-Mode Subscription Management System
"""

import logging
import asyncio
from typing import Dict, Any, List
from telegram.error import BadRequest, Forbidden

logger = logging.getLogger(__name__)

class SubscriptionManager:
    """Advanced 3-mode subscription system"""
    
    def __init__(self, db):
        self.db = db
        self._load_check_mode()
        logger.info(f"📢 Subscription check mode: {self.check_mode}")
    
    def _load_check_mode(self) -> None:
        """Load subscription check mode from database"""
        try:
            mode = self.db.get_bot_setting('subscription_check_mode', '1')
            self.check_mode = int(mode)
        except Exception as e:
            logger.error(f"Error loading check mode: {e}")
            self.check_mode = 1
    
    def get_check_mode(self) -> int:
        """Get current check mode"""
        self._load_check_mode()  # Always get fresh mode
        return self.check_mode
    
    def set_check_mode(self, mode: int, admin_id: int) -> bool:
        """Set subscription check mode"""
        try:
            if mode in [1, 2, 3]:
                if self.db.set_bot_setting('subscription_check_mode', str(mode)):
                    self.check_mode = mode
                    logger.info(f"📢 Subscription mode changed to {mode} by admin {admin_id}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error setting check mode: {e}")
            return False
    
    def get_check_mode_text(self, user_lang: str = 'uz') -> str:
        """Get check mode description"""
        mode = self.get_check_mode()
        
        if mode == 1:
            return "🟢 Rejim 1: Faqat /start da"
        elif mode == 2:
            return "🟡 Rejim 2: Har xabarda"
        elif mode == 3:
            return "🔴 Rejim 3: Har amalda"
        else:
            return "❓ Noma'lum rejim"
    
    async def should_check_subscription(self, user_id: int, action: str) -> bool:
        """Determine if subscription should be checked based on mode and action"""
        mode = self.get_check_mode()
        
        if mode == 1:  # Only on /start
            return action == 'start'
        elif mode == 2:  # On every message
            return action in ['start', 'message']
        elif mode == 3:  # On every action
            return action in ['start', 'message', 'action']
        
        return False
    
    async def check_subscription(self, user_id: int, bot) -> bool:
        """Check if user is subscribed to all mandatory channels"""
        try:
            channels = self.db.get_mandatory_channels()
            
            if not channels:
                return True  # No mandatory channels
            
            for channel in channels:
                try:
                    member = await bot.get_chat_member(channel['channel_id'], user_id)
                    if member.status in ['left', 'kicked']:
                        return False
                except (BadRequest, Forbidden):
                    # If we can't check, assume not subscribed
                    return False
                except Exception as e:
                    logger.error(f"Subscription check error for channel {channel['channel_id']}: {e}")
                    continue
            
            return True
            
        except Exception as e:
            logger.error(f"Subscription check error: {e}")
            return True  # On error, allow access
