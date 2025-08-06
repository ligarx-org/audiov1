"""
Advanced Broadcast Management System
"""

import logging
import asyncio
from typing import Dict, Any, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from languages import escape_markdown_v2

logger = logging.getLogger(__name__)

class BroadcastManager:
    """Advanced broadcast system with session management"""
    
    def __init__(self, db):
        self.db = db
        self.broadcast_sessions = {}  # Active broadcast sessions
        logger.info("📢 Broadcast Manager initialized")
    
    async def start_broadcast_session(self, admin_id: int, update, context) -> None:
        """Start a new broadcast session"""
        try:
            session_key = f"bc_{admin_id}"
            
            # Check if already in session
            if session_key in self.broadcast_sessions:
                await update.callback_query.answer("⚠️ Broadcast sessiyasi allaqachon faol!")
                return
            
            # Create new session
            self.broadcast_sessions[session_key] = {
                'admin_id': admin_id,
                'step': 'waiting_message',
                'message': None,
                'media_type': None,
                'media_file_id': None
            }
            
            await update.callback_query.answer("📢 Broadcast sessiyasi boshlandi!")
            await update.callback_query.edit_message_text(
                "📢 **BROADCAST XABAR YUBORISH**\n\n📝 **Xabar matnini yuboring:**\n\n• Matn xabar\n• Rasm + matn\n• Video + matn\n• Audio + matn\n\n❌ **Bekor qilish:** /cancel",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Broadcast session start error: {e}")
    
    async def handle_broadcast_message(self, update, context) -> None:
        """Handle broadcast message input"""
        try:
            admin_id = update.effective_user.id
            session_key = f"bc_{admin_id}"
            
            if session_key not in self.broadcast_sessions:
                return
            
            session = self.broadcast_sessions[session_key]
            
            if session['step'] == 'waiting_message':
                # Store message content
                if update.message.text:
                    session['message'] = update.message.text
                    session['media_type'] = 'text'
                elif update.message.photo:
                    session['message'] = update.message.caption or ""
                    session['media_type'] = 'photo'
                    session['media_file_id'] = update.message.photo[-1].file_id
                elif update.message.video:
                    session['message'] = update.message.caption or ""
                    session['media_type'] = 'video'
                    session['media_file_id'] = update.message.video.file_id
                elif update.message.audio:
                    session['message'] = update.message.caption or ""
                    session['media_type'] = 'audio'
                    session['media_file_id'] = update.message.audio.file_id
                else:
                    await update.message.reply_text("❌ Qo'llab-quvvatlanmaydigan fayl turi!")
                    return
                
                # Show confirmation
                await self._show_broadcast_confirmation(update, context, session)
            
        except Exception as e:
            logger.error(f"Broadcast message handling error: {e}")
    
    async def _show_broadcast_confirmation(self, update, context, session: Dict[str, Any]) -> None:
        """Show broadcast confirmation"""
        try:
            message = session['message']
            media_type = session['media_type']
            
            users = self.db.get_all_users()
            total_users = len(users)
            
            confirmation_text = f"📢 **BROADCAST TASDIQLASH**\n\n📊 **Jami foydalanuvchilar:** {total_users}\n\n📝 **Xabar turi:** {media_type.title()}\n\n**Xabar matni:**\n{escape_markdown_v2(message[:200])}{'...' if len(message) > 200 else ''}\n\n**Yuborishni tasdiqlaysizmi?**"
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Yuborish", callback_data=f"bc_confirm_{session['admin_id']}"),
                    InlineKeyboardButton("❌ Bekor qilish", callback_data=f"bc_cancel_{session['admin_id']}")
                ]
            ]
            
            await update.message.reply_text(
                confirmation_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Broadcast confirmation error: {e}")
    
    async def handle_broadcast_callback(self, update, context, data: str) -> None:
        """Handle broadcast callback queries"""
        try:
            query = update.callback_query
            admin_id = update.effective_user.id
            session_key = f"bc_{admin_id}"
            
            if data.startswith("bc_confirm_"):
                if session_key in self.broadcast_sessions:
                    session = self.broadcast_sessions[session_key]
                    await query.answer("📢 Broadcast boshlanmoqda...")
                    await self._execute_broadcast(update, context, session)
                else:
                    await query.answer("❌ Sessiya topilmadi!", show_alert=True)
            
            elif data.startswith("bc_cancel_"):
                if session_key in self.broadcast_sessions:
                    del self.broadcast_sessions[session_key]
                    await query.answer("❌ Broadcast bekor qilindi!")
                    await query.edit_message_text("❌ **Broadcast bekor qilindi!**", parse_mode=ParseMode.MARKDOWN)
                else:
                    await query.answer("❌ Sessiya topilmadi!", show_alert=True)
            
        except Exception as e:
            logger.error(f"Broadcast callback error: {e}")
    
    async def _execute_broadcast(self, update, context, session: Dict[str, Any]) -> None:
        """Execute the broadcast"""
        try:
            users = self.db.get_all_users()
            message = session['message']
            media_type = session['media_type']
            media_file_id = session.get('media_file_id')
            
            sent_count = 0
            failed_count = 0
            
            # Update initial message
            status_message = await update.callback_query.edit_message_text(
                f"📢 **BROADCAST JARAYONI**\n\n📊 **Jami:** {len(users)}\n✅ **Yuborildi:** {sent_count}\n❌ **Xato:** {failed_count}\n\n⏳ **Jarayon davom etmoqda...**",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Send to all users
            for i, user in enumerate(users):
                try:
                    user_id = user['user_id']
                    
                    if media_type == 'text':
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    elif media_type == 'photo':
                        await context.bot.send_photo(
                            chat_id=user_id,
                            photo=media_file_id,
                            caption=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    elif media_type == 'video':
                        await context.bot.send_video(
                            chat_id=user_id,
                            video=media_file_id,
                            caption=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    elif media_type == 'audio':
                        await context.bot.send_audio(
                            chat_id=user_id,
                            audio=media_file_id,
                            caption=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    
                    sent_count += 1
                    
                except (BadRequest, Forbidden):
                    failed_count += 1
                except Exception as e:
                    logger.error(f"Broadcast send error to {user_id}: {e}")
                    failed_count += 1
                
                # Update status every 50 users
                if (i + 1) % 50 == 0:
                    try:
                        await status_message.edit_text(
                            f"📢 **BROADCAST JARAYONI**\n\n📊 **Jami:** {len(users)}\n✅ **Yuborildi:** {sent_count}\n❌ **Xato:** {failed_count}\n\n⏳ **Jarayon davom etmoqda... ({i+1}/{len(users)})**",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.05)
            
            # Final status
            await status_message.edit_text(
                f"✅ **BROADCAST YAKUNLANDI!**\n\n📊 **Jami:** {len(users)}\n✅ **Yuborildi:** {sent_count}\n❌ **Xato:** {failed_count}\n\n🎯 **Muvaffaqiyat:** {(sent_count/len(users)*100):.1f}%",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Clean up session
            session_key = f"bc_{session['admin_id']}"
            if session_key in self.broadcast_sessions:
                del self.broadcast_sessions[session_key]
            
        except Exception as e:
            logger.error(f"Broadcast execution error: {e}")
