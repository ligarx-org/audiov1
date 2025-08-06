import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.error import BadRequest, Forbidden, TimedOut, InvalidToken
from telegram.constants import ParseMode
import threading
from concurrent.futures import ThreadPoolExecutor
import time

from database import DatabaseManager
from languages import get_text, detect_language, LANGUAGES, escape_markdown_v2
from shazam import ShazamRecognizer
from messenger import MessengerDownloader
from search import FastMusicSearcher
from admin import AdvancedAdminPanel
from subscription import SubscriptionManager
from premium import PremiumManager
from broadcast import BroadcastManager

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "7662375001:AAEfHtFy78deU5YfOSNn-qF49UBn5J9uqkw"
MEGA_ADMIN_ID = 6547102814
SONGS_PER_PAGE = 10
MAX_CONCURRENT_USERS = 1000

class UltraFastMusicBot:
    def __init__(self):
        logger.info("🚀 Initializing Ultra-Fast Music Bot...")
        
        try:
            logger.info("📊 Initializing database...")
            self.db = DatabaseManager()
            
            logger.info("🎙️ Initializing Shazam recognizer...")
            self.shazam = ShazamRecognizer()
            
            logger.info("📱 Initializing messenger downloader...")
            self.messenger = MessengerDownloader()
            
            logger.info("🔍 Initializing fast music searcher...")
            self.searcher = FastMusicSearcher()
            
            logger.info("💎 Initializing premium manager...")
            self.premium = PremiumManager(self.db)
            
            logger.info("📢 Initializing subscription manager...")
            self.subscription = SubscriptionManager(self.db)
            
            logger.info("📢 Initializing broadcast manager...")
            self.broadcast = BroadcastManager(self.db)
            
            logger.info("👑 Initializing advanced admin panel...")
            self.admin = AdvancedAdminPanel(self.db, MEGA_ADMIN_ID, self.broadcast)
            
            self.main_executor = ThreadPoolExecutor(max_workers=50, thread_name_prefix="main")
            self.download_executor = ThreadPoolExecutor(max_workers=30, thread_name_prefix="download")
            self.recognition_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="recognition")
            
            self.user_sessions = {}
            self.session_lock = threading.Lock()
            self.rate_limits = {}
            self.rate_limit_lock = threading.Lock()
            
            logger.info("✅ Ultra-Fast Music Bot initialized successfully!")
            
        except Exception as e:
            logger.error(f"❌ Error initializing bot: {e}")
            raise
    
    def is_rate_limited(self, user_id: int) -> bool:
        with self.rate_limit_lock:
            now = time.time()
            if user_id in self.rate_limits:
                last_request, count = self.rate_limits[user_id]
                if now - last_request < 60:
                    if count >= 50:
                        return True
                    self.rate_limits[user_id] = (last_request, count + 1)
                else:
                    self.rate_limits[user_id] = (now, 1)
            else:
                self.rate_limits[user_id] = (now, 1)
            return False
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not user:
            return
        
        user_id = user.id
        
        if self.is_rate_limited(user_id):
            return
        
        asyncio.create_task(self._register_user_background(user_id, user.username, user.first_name, user.last_name))
        
        if self.db.is_user_banned(user_id):
            ban_info = self.db.get_ban_info(user_id)
            await update.message.reply_text(
                get_text('banned_message', 'uz').format(
                    reason=escape_markdown_v2(ban_info.get('reason', 'Noma\'lum')),
                    date=escape_markdown_v2(ban_info.get('date', 'Noma\'lum'))
                ),
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        
        current_lang = self.db.get_user_language(user_id)
        
        if current_lang and current_lang in LANGUAGES:
            if self.admin.is_admin(user_id):
                await self.show_admin_welcome(update, context, current_lang)
            else:
                should_check = await self.subscription.should_check_subscription(user_id, 'start')
                if should_check and not await self.subscription.check_subscription(user_id, context.bot):
                    await self.show_subscription_message(update, current_lang)
                else:
                    await self.show_user_welcome(update, context, current_lang, user.first_name)
        else:
            await self.show_language_selection(update, context)
        
        asyncio.create_task(self._log_activity_background(user_id, 'start'))
    
    async def _register_user_background(self, user_id: int, username: str, first_name: str, last_name: str) -> None:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self.main_executor,
                self.db.add_user,
                user_id, username, first_name, last_name
            )
        except Exception as e:
            logger.error(f"Background user registration error: {e}")
    
    async def _log_activity_background(self, user_id: int, activity_type: str, data: Dict[str, Any] = None, platform: str = None, success: bool = True) -> None:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self.main_executor, 
                self.db.log_user_activity, 
                user_id, 
                activity_type, 
                data,
                platform,
                success
            )
        except Exception as e:
            logger.error(f"Background logging error: {e}")
    
    async def show_language_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        keyboard = [
            [
                InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz"),
                InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")
            ],
            [
                InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            get_text('select_language', 'uz'),
            reply_markup=reply_markup
        )
    
    async def show_admin_welcome(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_lang: str) -> None:
        stats = self.db.get_statistics()
        premium_mode = "🟢 Yoqilgan" if self.premium.is_premium_mode_enabled() else "🔴 O'chirilgan"
        check_mode = self.subscription.get_check_mode_text(user_lang)
        banned_count = len(self.db.get_banned_users(page=1, per_page=1000)['users'])
        admin_count = len(self.db.get_admins())
        channel_count = len(self.db.get_mandatory_channels())
        
        message = f"""👑 ADMIN BOSHQARUV PANELIga xush kelibsiz!

📊 Tezkor Statistika:
• 👥 Jami foydalanuvchilar: {stats.get('total_users', 0)}
• 🟢 Bugun faol: {stats.get('active_today', 0)}
• 🔍 Jami qidiruvlar: {stats.get('total_searches', 0)}
• ⬇️ Jami yuklab olishlar: {stats.get('total_downloads', 0)}
• 🎙️ Jami tanishlar: {stats.get('total_recognitions', 0)}

⚙️ Tizim holati:
• 💎 Premium rejim: {premium_mode}
• 📢 Majburiy azolik: {check_mode}
• 🚫 Bloklangan: {banned_count}
• 👑 Adminlar: {admin_count}
• 📢 Majburiy kanallar: {channel_count}

🛠️ To'liq boshqaruv paneli orqali botni nazorat qiling!"""
        
        keyboard = [
            [
                InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel"),
                InlineKeyboardButton("👤 Foydalanuvchi rejimi", callback_data="user_mode")
            ],
            [
                InlineKeyboardButton("📢 Tezkor xabar", callback_data="admin_broadcast"),
                InlineKeyboardButton("💎 Premium", callback_data="admin_premium")
            ],
            [
                InlineKeyboardButton("🚫 Ban boshqaruvi", callback_data="admin_ban"),
                InlineKeyboardButton("📢 Majburiy azolik", callback_data="admin_subscription")
            ],
            [
                InlineKeyboardButton("👑 Adminlar", callback_data="admin_admins"),
                InlineKeyboardButton("📊 Batafsil Statistika", callback_data="admin_stats")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup
        )
    
    async def show_user_welcome(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_lang: str, name: str) -> None:
        keyboard = [
            [
                InlineKeyboardButton(get_text('search_music', user_lang), callback_data="search_music"),
                InlineKeyboardButton(get_text('recognize_song', user_lang), callback_data="recognize_song")
            ],
            [
                InlineKeyboardButton(get_text('download_media', user_lang), callback_data="download_media"),
                InlineKeyboardButton(get_text('help', user_lang), callback_data="help")
            ]
        ]
        
        welcome_text = get_text('welcome_message', user_lang).format(name=name or "Foydalanuvchi")
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_language_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data:
            return
        
        user_id = update.effective_user.id
        language = query.data.split('_')[1]
        
        if language in LANGUAGES:
            asyncio.create_task(self._set_language_background(user_id, language))
            await query.answer(get_text('language_selected', language))
            
            if self.admin.is_admin(user_id):
                await self.show_admin_welcome_inline(update, context, language)
            else:
                should_check = await self.subscription.should_check_subscription(user_id, 'start')
                if should_check and not await self.subscription.check_subscription(user_id, context.bot):
                    await self.show_subscription_message_inline(update, language)
                else:
                    await self.show_user_welcome_inline(update, context, language, update.effective_user.first_name)
    
    async def _set_language_background(self, user_id: int, language: str) -> None:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self.main_executor,
                self.db.set_user_language,
                user_id, language
            )
        except Exception as e:
            logger.error(f"Background language setting error: {e}")
    
    async def show_admin_welcome_inline(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_lang: str) -> None:
        stats = self.db.get_statistics()
        premium_mode = "🟢 Yoqilgan" if self.premium.is_premium_mode_enabled() else "🔴 O'chirilgan"
        check_mode = self.subscription.get_check_mode_text(user_lang)
        banned_count = len(self.db.get_banned_users(page=1, per_page=1000)['users'])
        admin_count = len(self.db.get_admins())
        channel_count = len(self.db.get_mandatory_channels())
        
        message = f"""👑 ADMIN BOSHQARUV PANELIga xush kelibsiz!

📊 Tezkor Statistika:
• 👥 Jami foydalanuvchilar: {stats.get('total_users', 0)}
• 🟢 Bugun faol: {stats.get('active_today', 0)}
• 🔍 Jami qidiruvlar: {stats.get('total_searches', 0)}
• ⬇️ Jami yuklab olishlar: {stats.get('total_downloads', 0)}
• 🎙️ Jami tanishlar: {stats.get('total_recognitions', 0)}

⚙️ Tizim holati:
• 💎 Premium rejim: {premium_mode}
• 📢 Majburiy azolik: {check_mode}
• 🚫 Bloklangan: {banned_count}
• 👑 Adminlar: {admin_count}
• 📢 Majburiy kanallar: {channel_count}

🛠️ To'liq boshqaruv paneli orqali botni nazorat qiling!"""
        
        keyboard = [
            [
                InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel"),
                InlineKeyboardButton("👤 Foydalanuvchi rejimi", callback_data="user_mode")
            ],
            [
                InlineKeyboardButton("📢 Tezkor xabar", callback_data="admin_broadcast"),
                InlineKeyboardButton("💎 Premium", callback_data="admin_premium")
            ],
            [
                InlineKeyboardButton("🚫 Ban boshqaruvi", callback_data="admin_ban"),
                InlineKeyboardButton("📢 Majburiy azolik", callback_data="admin_subscription")
            ],
            [
                InlineKeyboardButton("👑 Adminlar", callback_data="admin_admins"),
                InlineKeyboardButton("📊 Batafsil Statistika", callback_data="admin_stats")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=reply_markup
        )
    
    async def show_user_welcome_inline(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_lang: str, name: str) -> None:
        keyboard = [
            [
                InlineKeyboardButton(get_text('search_music', user_lang), callback_data="search_music"),
                InlineKeyboardButton(get_text('recognize_song', user_lang), callback_data="recognize_song")
            ],
            [
                InlineKeyboardButton(get_text('download_media', user_lang), callback_data="download_media"),
                InlineKeyboardButton(get_text('help', user_lang), callback_data="help")
            ]
        ]
        
        welcome_text = get_text('welcome_message', user_lang).format(name=name or "Foydalanuvchi")
        
        await update.callback_query.edit_message_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_subscription_message(self, update: Update, user_lang: str) -> None:
        channels = self.db.get_mandatory_channels()
        if not channels:
            return
        
        keyboard = []
        for channel in channels:
            keyboard.append([InlineKeyboardButton(
                get_text('check_subscription', user_lang),
                url=f"https://t.me/{channel['username'].replace('@', '')}"
            )])
        keyboard.append([InlineKeyboardButton(
            get_text('verify_subscription', user_lang),
            callback_data="verify_subscription"
        )])
        
        await update.message.reply_text(
            get_text('mandatory_subscription', user_lang),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_subscription_message_inline(self, update: Update, user_lang: str) -> None:
        channels = self.db.get_mandatory_channels()
        if not channels:
            await self.show_user_welcome_inline(update, None, user_lang, update.effective_user.first_name)
            return
        
        keyboard = []
        for channel in channels:
            keyboard.append([InlineKeyboardButton(
                get_text('check_subscription', user_lang),
                url=f"https://t.me/{channel['username'].replace('@', '')}"
            )])
        keyboard.append([InlineKeyboardButton(
            get_text('verify_subscription', user_lang),
            callback_data="verify_subscription"
        )])
        
        await update.callback_query.edit_message_text(
            get_text('mandatory_subscription', user_lang),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return
        
        user_id = update.effective_user.id
        user_lang = self.db.get_user_language(user_id)
        
        if self.admin.is_admin(user_id):
            if f"bc_{user_id}" in self.broadcast.broadcast_sessions:
                await self.broadcast.handle_broadcast_message(update, context)
                return
            elif user_id in self.admin.admin_states:
                await self.admin.handle_admin_message(update, context)
                return
        
        if self.is_rate_limited(user_id):
            await update.message.reply_text("⚠️ Juda tez! Biroz kuting...")
            return
        
        if self.db.is_user_banned(user_id):
            return
        
        if not self.admin.is_admin(user_id):
            should_check = await self.subscription.should_check_subscription(user_id, 'message')
            if should_check:
                subscription_check = asyncio.create_task(
                    self.subscription.check_subscription(user_id, context.bot)
                )
                try:
                    is_subscribed = await asyncio.wait_for(subscription_check, timeout=5.0)
                    if not is_subscribed:
                        await self.show_subscription_message(update, user_lang)
                        return
                except asyncio.TimeoutError:
                    logger.warning(f"Subscription check timeout for user {user_id}")
        
        text = update.message.text.strip()
        
        if text == '/cancel' and self.admin.is_admin(user_id) and user_id in self.admin.admin_states:
            del self.admin.admin_states[user_id]
            await update.message.reply_text("❌ Amal bekor qilindi!")
            return
        
        if self.is_url(text):
            asyncio.create_task(self._handle_url_background(update, context, text, user_lang))
        else:
            asyncio.create_task(self._handle_search_background(update, context, text, user_lang))
    
    async def _handle_url_background(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, user_lang: str) -> None:
        try:
            await self.messenger.handle_url(update, context, url, user_lang)
        except Exception as e:
            logger.error(f"Background URL handling error: {e}")
    
    async def _handle_search_background(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, user_lang: str) -> None:
        try:
            await self.handle_instant_search(update, context, query)
        except Exception as e:
            logger.error(f"Background search error: {e}")
    
    async def handle_instant_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
        user_id = update.effective_user.id
        user_lang = self.db.get_user_language(user_id)
        is_premium = self.premium.is_premium_mode_enabled()
        
        if not query.strip():
            await update.message.reply_text("❌ Qidiruv so'zini kiriting!")
            return
        
        logger.info(f"🔍 Instant search by {user_id}: {query}")
        
        loading_message = await update.message.reply_text(
            f"🔍 Qidirilmoqda: {query}\n⚡ YouTube Music dan tezkor natijalar..."
        )
        
        try:
            limit = 50 if is_premium else 30
            
            loop = asyncio.get_running_loop()
            songs = await loop.run_in_executor(
                self.main_executor,
                self._search_music_sync,
                query, limit
            )
            
            if not songs:
                await loading_message.edit_text(f"❌ {query} uchun natija topilmadi.\n\n💡 Boshqa so'zlar bilan sinab ko'ring!")
                asyncio.create_task(self._log_activity_background(
                    user_id, 'search', {'query': query, 'results': 0}, success=False
                ))
                return
            
            with self.session_lock:
                self.user_sessions[user_id] = {
                    'search_results': songs,
                    'search_query': query,
                    'current_page': 1,
                    'total': len(songs)
                }
            
            await loading_message.delete()
            await self.display_search_results_fast(update, context, user_id, 1)
            
            asyncio.create_task(self._log_activity_background(
                user_id, 'search', {'query': query, 'results': len(songs)}, success=True
            ))
            
        except Exception as e:
            logger.error(f"❌ Instant search error: {e}")
            await loading_message.edit_text("❌ Qidirishda xatolik yuz berdi.")
            asyncio.create_task(self._log_activity_background(
                user_id, 'search', {'query': query, 'error': str(e)}, success=False
            ))
    
    def _search_music_sync(self, query: str, limit: int) -> list:
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.searcher.search_music_fast(query, limit))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Sync search error: {e}")
            return []
    
    async def display_search_results_fast(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, page: int) -> None:
        user_lang = self.db.get_user_language(user_id)
        is_premium = self.premium.is_premium_mode_enabled()
        
        with self.session_lock:
            session = self.user_sessions.get(user_id, {})
        
        songs = session.get('search_results', [])
        query = session.get('search_query', '')
        total = session.get('total', 0)
        
        if not songs:
            return
        
        start_idx = (page - 1) * SONGS_PER_PAGE
        end_idx = start_idx + SONGS_PER_PAGE
        page_songs = songs[start_idx:end_idx]
        total_pages = (total + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
        
        if not page_songs:
            return
        
        premium_badge = "💎" if is_premium else "⭐"
        message_text = f"""🎵 "{query}" uchun natijalar {premium_badge}
📄 Sahifa {page}/{total_pages} (Jami: {total} natija)

"""
        
        for idx, song in enumerate(page_songs, start=start_idx + 1):
            duration = int(song.get("duration", 0))
            duration_text = f"{duration//60}:{duration%60:02d}" if duration > 0 else "N/A"
            music_badge = "🎵" if song.get('is_music') else "📹"
            view_count = song.get('view_count', 0)
            view_text = f"{view_count:,}" if view_count > 0 else "N/A"
            
            message_text += f"""{idx}. {music_badge} {song.get('title', 'Unknown')}
👤 {song.get('artist', 'Unknown')} • ⏱️ {duration_text} • 👁️ {view_text}

"""
        
        keyboard = []
        
        # Only show individual song buttons
        buttons_row1 = []
        for idx in range(start_idx, min(start_idx + 5, end_idx)):
            if idx < len(songs):
                buttons_row1.append(InlineKeyboardButton(str(idx + 1), callback_data=f"download_song_{idx}"))
        
        buttons_row2 = []
        for idx in range(start_idx + 5, min(start_idx + 10, end_idx)):
            if idx < len(songs):
                buttons_row2.append(InlineKeyboardButton(str(idx + 1), callback_data=f"download_song_{idx}"))
        
        if buttons_row1:
            keyboard.append(buttons_row1)
        if buttons_row2:
            keyboard.append(buttons_row2)
        
        # Navigation buttons
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ Orqaga", callback_data=f"page_{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"page_{page+1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(
                    message_text,
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    message_text,
                    reply_markup=reply_markup
                )
        except BadRequest as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Display error: {e}")
    
    async def handle_audio_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not (update.message.audio or update.message.video or update.message.voice or update.message.photo):
            return
        
        user_id = update.effective_user.id
        user_lang = self.db.get_user_language(user_id)
        
        if self.admin.is_admin(user_id) and f"bc_{user_id}" in self.broadcast.broadcast_sessions:
            await self.broadcast.handle_broadcast_message(update, context)
            return
        
        if self.is_rate_limited(user_id):
            await update.message.reply_text("⚠️ Juda tez! Biroz kuting...")
            return
        
        if self.db.is_user_banned(user_id):
            return
        
        if not self.admin.is_admin(user_id):
            should_check = await self.subscription.should_check_subscription(user_id, 'action')
            if should_check:
                subscription_check = asyncio.create_task(
                    self.subscription.check_subscription(user_id, context.bot)
                )
                try:
                    is_subscribed = await asyncio.wait_for(subscription_check, timeout=5.0)
                    if not is_subscribed:
                        await self.show_subscription_message(update, user_lang)
                        return
                except asyncio.TimeoutError:
                    logger.warning(f"Subscription check timeout for user {user_id}")
        
        if update.message.audio or update.message.video or update.message.voice:
            loading_message = await update.message.reply_text(get_text('recognizing_audio', user_lang))
            
            asyncio.create_task(self._process_audio_recognition_background(
                update, context, loading_message, user_id, user_lang
            ))
    
    async def _process_audio_recognition_background(self, update, context, loading_message, user_id, user_lang):
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                self.recognition_executor,
                self._recognize_audio_sync,
                update.message, user_lang
            )
            
            if result["success"]:
                track_info = result["track_info"]
                
                message = f"""🎵 {get_text('recognition_success', user_lang)}

🎤 Nomi: {track_info['title']}
👤 Ijrochi: {track_info['artist']}
💿 Albom: {track_info['album']}
⏱️ Vaqt: {result['duration']:.2f}s"""
                
                keyboard = [[InlineKeyboardButton(
                    "🔍 Bu qo'shiqni qidirish",
                    callback_data=f"search_recognized_{track_info['title']} {track_info['artist']}"
                )]]
                
                if track_info.get('cover_url'):
                    try:
                        await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo=track_info['cover_url'],
                            caption=message,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                        await loading_message.delete()
                    except Exception:
                        await loading_message.edit_text(
                            message,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                else:
                    await loading_message.edit_text(
                        message,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                
                asyncio.create_task(self._log_activity_background(
                    user_id, 'recognize', {
                        'title': track_info['title'],
                        'artist': track_info['artist']
                    }, success=True
                ))
            else:
                await loading_message.edit_text(
                    f"❌ {get_text('recognition_failed', user_lang)}\n⏱️ Vaqt: {result['duration']:.2f}s\n\n💡 Boshqa qismini sinab ko'ring!"
                )
                
                asyncio.create_task(self._log_activity_background(
                    user_id, 'recognize', {
                        'error': result.get('error', 'Unknown error')
                    }, success=False
                ))
        
        except Exception as e:
            logger.error(f"Recognition error: {e}")
            await loading_message.edit_text("❌ Tanishda xatolik yuz berdi.")
            asyncio.create_task(self._log_activity_background(
                user_id, 'recognize', {'error': str(e)}, success=False
            ))
    
    def _recognize_audio_sync(self, message, user_lang: str) -> dict:
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.shazam.recognize_from_telegram(message, user_lang))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Sync recognition error: {e}")
            return {
                "success": False,
                "track_info": {},
                "duration": 0,
                "error": str(e)
            }
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data:
            return
        
        user_id = update.effective_user.id
        user_lang = self.db.get_user_language(user_id)
        data = query.data
        
        try:
            if data.startswith("lang_"):
                await self.handle_language_selection(update, context)
            
            elif data == "user_mode":
                await query.answer()
                await self.show_user_welcome_inline(update, context, user_lang, update.effective_user.first_name)
            
            elif data == "verify_subscription":
                subscription_check = asyncio.create_task(
                    self.subscription.check_subscription(user_id, context.bot)
                )
                try:
                    is_subscribed = await asyncio.wait_for(subscription_check, timeout=10.0)
                    if is_subscribed:
                        await query.answer("✅ Tasdiqlandi!")
                        await self.show_user_welcome_inline(update, context, user_lang, update.effective_user.first_name)
                    else:
                        await query.answer("❌ Hali ham a'zo emassiz!", show_alert=True)
                except asyncio.TimeoutError:
                    await query.answer("⏰ Tekshirish vaqti tugadi, qayta urinib ko'ring!", show_alert=True)
            
            elif data.startswith("page_"):
                page = int(data.split("_")[1])
                await query.answer()
                await self.display_search_results_fast(update, context, user_id, page)
            
            elif data.startswith("download_song_"):
                song_idx = int(data.split("_")[2])
                await self.download_song_instant(update, context, user_id, song_idx)
            
            elif data.startswith("search_recognized_"):
                search_query = data.split("_", 2)[2]
                await query.answer("🔍 Qidirilmoqda...")
                
                class FakeMessage:
                    def __init__(self, text):
                        self.text = text
                    async def reply_text(self, text, **kwargs):
                        return await query.message.reply_text(text, **kwargs)
                
                class FakeUpdate:
                    def __init__(self, message, user):
                        self.message = message
                        self.effective_user = user
                        self.effective_chat = query.message.chat
                
                fake_update = FakeUpdate(FakeMessage(search_query), update.effective_user)
                asyncio.create_task(self._handle_search_background(fake_update, context, search_query, user_lang))
            
            elif data.startswith("admin_") or data.startswith("ban_") or data.startswith("sub_") or data.startswith("premium_") or data.startswith("admins_") or data.startswith("settings_") or data.startswith("users_"):
                await self.admin.handle_callback(update, context, data)
            
            elif data.startswith("bc_"):
                await self.broadcast.handle_broadcast_callback(update, context, data)
            
            elif data == "help":
                await self.show_help(update, context)
            
            elif data == "search_music":
                await query.answer()
                await query.edit_message_text(
                    "🔍 Musiqa qidirish\n\nQo'shiq nomini yozing va men YouTube Music dan tezkor qidirib beraman!\n\nMisol: Adele Hello\n\n⚡ Juda tez natija!"
                )
            
            elif data == "recognize_song":
                await query.answer()
                await query.edit_message_text(
                    "🎙️ Qo'shiqni tanib olish\n\nAudio fayl yuboring va men uni darhol tanib beraman!\n\n📱 Qo'llab-quvvatlanadigan:\n• 🎵 Audio (MP3, WAV, M4A)\n• 🎬 Video (MP4, AVI, MOV)\n• 🎤 Ovozli xabar\n\n⚡ Shazam orqali tezkor tanish!"
                )
            
            elif data == "download_media":
                await query.answer()
                await query.edit_message_text(
                    "📱 Media yuklab olish\n\nQuyidagi platformalardan havolalarni yuboring:\n\n• 📺 YouTube - video va audio\n• 📸 Instagram - reels va postlar\n• 🎵 TikTok - videolar\n\n⚡ Tezkor yuklab olish!"
                )
            
            elif data == "back_to_menu":
                await query.answer()
                if self.admin.is_admin(user_id):
                    await self.show_admin_welcome_inline(update, context, user_lang)
                else:
                    await self.show_user_welcome_inline(update, context, user_lang, update.effective_user.first_name)
            
            else:
                await self.messenger.handle_callback(update, context, data, user_lang)
        
        except Exception as e:
            logger.error(f"Callback error: {e}")
            try:
                await query.answer("❌ Xatolik yuz berdi!", show_alert=True)
            except:
                pass
    
    async def download_song_instant(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, song_idx: int) -> None:
        user_lang = self.db.get_user_language(user_id)
        is_premium = self.premium.is_premium_mode_enabled()
        
        with self.session_lock:
            session = self.user_sessions.get(user_id, {})
        
        songs = session.get('search_results', [])
        
        if song_idx >= len(songs):
            await update.callback_query.answer("❌ Yaroqsiz tanlov!", show_alert=True)
            return
        
        song = songs[song_idx]
        
        await update.callback_query.answer(f"⏳ Yuklanmoqda: {song['title']}")
        
        # Send loading message
        loading_message = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⏳ **Yuklab olinyapti...**\n\n🎵 {song['title']}\n👤 {song['artist']}\n\n📥 Tezda tayyor bo'ladi!",
            parse_mode=ParseMode.MARKDOWN
        )
        
        asyncio.create_task(self._download_song_background(
            song, update.effective_chat.id, context, user_lang, is_premium, user_id, loading_message
        ))
    
    async def _download_song_background(self, song: dict, chat_id: int, context, user_lang: str, is_premium: bool, user_id: int, loading_message) -> None:
        try:
            await self.searcher.download_song_background(
                song=song,
                chat_id=chat_id,
                context=context,
                user_lang=user_lang,
                is_premium=is_premium,
                loading_message=loading_message
            )
            
            platform = 'youtube'
            asyncio.create_task(self._log_activity_background(
                user_id, 'download', {
                    'title': song['title'],
                    'artist': song['artist']
                }, platform=platform, success=True
            ))
            
        except Exception as e:
            logger.error(f"Background download error: {e}")
            try:
                await loading_message.edit_text("❌ Yuklab olishda xatolik yuz berdi!")
            except:
                pass
            asyncio.create_task(self._log_activity_background(
                user_id, 'download', {
                    'title': song['title'],
                    'artist': song['artist'],
                    'error': str(e)
                }, success=False
            ))
    
    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        user_lang = self.db.get_user_language(user_id)
        
        help_text = f"""❓ Yordam

🎵 Ultra-Fast Music Bot - eng tez musiqa bot!

🚀 Asosiy funksiyalar:
• 🔍 YouTube Music dan tezkor qidirish
• 🎙️ Audio tanib olish (Shazam)
• 📱 Instagram, TikTok, YouTube yuklab olish
• 🎧 MP3/MP4 formatda yuklab olish

⚡ Qanday foydalanish:
1. Qo'shiq nomini yozing - darhol qidiradi
2. Audio fayl yuboring - tezkor taniydi
3. Havola yuboring - zudlik bilan yuklaydi

📞 Qo'llab-quvvatlash: @{self.db.get_bot_setting('support_admin', 'support_admin')}"""
        
        keyboard = [[InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_menu")]]
        
        await update.callback_query.edit_message_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    def is_url(self, text: str) -> bool:
        try:
            from urllib.parse import urlparse
            result = urlparse(text)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except:
            return False
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        
        if not self.admin.is_admin(user_id):
            return
        
        await self.admin.show_admin_panel(update, context)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        user_lang = self.db.get_user_language(user_id)
        
        if not self.admin.is_admin(user_id):
            return
        
        stats = self.db.get_statistics()
        
        message = f"""📊 Batafsil Statistika

👥 Foydalanuvchilar:
• Jami: {stats.get('total_users', 0)}
• Bugun faol: {stats.get('active_today', 0)}
• Hafta faol: {stats.get('active_week', 0)}
• Oy faol: {stats.get('active_month', 0)}

📈 Faoliyat:
• Jami qidiruvlar: {stats.get('total_searches', 0)}
• Bugun qidiruvlar: {stats.get('searches_today', 0)}
• Hafta qidiruvlar: {stats.get('searches_week', 0)}
• Oy qidiruvlar: {stats.get('searches_month', 0)}

• Jami yuklab olishlar: {stats.get('total_downloads', 0)}
• Bugun yuklab olishlar: {stats.get('downloads_today', 0)}
• Hafta yuklab olishlar: {stats.get('downloads_week', 0)}
• Oy yuklab olishlar: {stats.get('downloads_month', 0)}

• Jami tanishlar: {stats.get('total_recognitions', 0)}
• Bugun tanishlar: {stats.get('recognitions_today', 0)}
• Hafta tanishlar: {stats.get('recognitions_week', 0)}
• Oy tanishlar: {stats.get('recognitions_month', 0)}

🎵 Platform:
• YouTube yuklab olishlar: {stats.get('youtube_downloads', 0)}
• Instagram yuklab olishlar: {stats.get('instagram_downloads', 0)}
• TikTok yuklab olishlar: {stats.get('tiktok_downloads', 0)}"""
        
        await update.message.reply_text(message)
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        
        if user_id != MEGA_ADMIN_ID:
            return
        
        if not context.args:
            await update.message.reply_text("📢 Xabar matnini kiriting: /broadcast <xabar>")
            return
        
        message = " ".join(context.args)
        users = self.db.get_all_users()
        
        sent = 0
        failed = 0
        
        status_message = await update.message.reply_text("📢 Xabar yuborilmoqda...")
        
        async def send_broadcast():
            nonlocal sent, failed
            for user in users:
                try:
                    await context.bot.send_message(chat_id=user['user_id'], text=message)
                    sent += 1
                except Exception:
                    failed += 1
                
                if (sent + failed) % 100 == 0:
                    try:
                        await status_message.edit_text(
                            f"📊 Yuborildi: {sent}\n❌ Xato: {failed}\n📈 Jami: {len(users)}"
                        )
                    except:
                        pass
                
                await asyncio.sleep(0.1)
            
            await status_message.edit_text(
                f"✅ Yakunlandi!\n📊 Yuborildi: {sent}\n❌ Xato: {failed}"
            )
        
        asyncio.create_task(send_broadcast())
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error(f"Exception: {context.error}")
        
        if isinstance(update, Update) and update.effective_chat:
            try:
                user_id = update.effective_user.id if update.effective_user else 0
                user_lang = self.db.get_user_language(user_id) if user_id else 'uz'
                
                pass
            except Exception:
                pass
    
    async def setup_bot_commands(self, application: Application) -> None:
        try:
            commands = [
                BotCommand("start", "Botni ishga tushirish"),
                BotCommand("admin", "Admin panel (faqat adminlar uchun)"),
                BotCommand("stats", "Statistika (faqat adminlar uchun)"),
            ]
            
            await application.bot.set_my_commands(commands)
            logger.info("✅ Bot commands set successfully")
        except Exception as e:
            logger.error(f"❌ Error setting bot commands: {e}")
    
    def run(self) -> None:
        logger.info("🚀 Starting Ultra-Fast Music Bot...")
        
        try:
            logger.info("📡 Building Telegram Application...")
            application = Application.builder().token(TELEGRAM_TOKEN).build()
            application.bot_data['bot_instance'] = self # Make bot instance accessible
            logger.info("✅ Telegram Application built successfully")
        except InvalidToken:
            logger.critical("❌ FATAL ERROR: Invalid Telegram Bot Token!")
            return
        except Exception as e:
            logger.critical(f"❌ FATAL ERROR: {e}")
            return
        
        try:
            application.add_error_handler(self.error_handler)
            
            logger.info("🔧 Adding handlers...")
            application.add_handler(CommandHandler("start", self.start))
            application.add_handler(CommandHandler("admin", self.admin_command))
            application.add_handler(CommandHandler("stats", self.stats_command))
            application.add_handler(CommandHandler("broadcast", self.broadcast_command))
            
            application.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND, 
                self.handle_text_message
            ))
            application.add_handler(MessageHandler(
                filters.AUDIO | filters.VIDEO | filters.VOICE | filters.PHOTO, 
                self.handle_audio_file
            ))
            
            application.add_handler(CallbackQueryHandler(self.handle_callback_query))
            
            logger.info("✅ All handlers added successfully")
            
            async def setup_commands(application):
                await self.setup_bot_commands(application)
            
            application.post_init = setup_commands
            
            logger.info("🎵 Ultra-Fast Music Bot is ready!")
            logger.info("⚡ Instant responses enabled")
            logger.info("🔄 Background processing active")
            logger.info("💎 Premium system enabled")
            logger.info("📢 Advanced broadcast system ready")
            logger.info("🎯 Accurate search results from YouTube Music")
            logger.info("📊 Perfect pagination (10 per page)")
            logger.info("👑 Advanced admin panel with all features")
            logger.info("📢 3-mode subscription system")
            logger.info("🚫 Advanced ban system with ID support")
            logger.info("📊 Comprehensive statistics tracking")
            logger.info("🎙️ Enhanced Shazam recognition")
            logger.info("🚀 Starting polling...")
            
            application.run_polling(drop_pending_updates=True)
            
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Bot error: {e}")
        finally:
            logger.info("🧹 Cleaning up...")
            self.main_executor.shutdown(wait=True)
            self.download_executor.shutdown(wait=True)
            self.recognition_executor.shutdown(wait=True)
            if hasattr(self, 'db'):
                self.db.close()
            logger.info("✅ Cleanup completed")

def main() -> None:
    print("🎵 Ultra-Fast Music Bot")
    print("=" * 50)
    
    os.makedirs("temp/bot", exist_ok=True)
    os.makedirs("temp/messenger", exist_ok=True)
    os.makedirs("temp/shazam", exist_ok=True)
    os.makedirs("temp/downloads", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    try:
        bot = UltraFastMusicBot()
        bot.run()
    except Exception as e:
        logger.critical(f"❌ CRITICAL ERROR: {e}")
        print(f"\n❌ Bot failed to start: {e}")

if __name__ == "__main__":
    main()
