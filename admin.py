import logging
import asyncio
from typing import Dict, Any, List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

logger = logging.getLogger(__name__)

class AdvancedAdminPanel:
    def __init__(self, db, mega_admin_id: int, broadcast_manager):
        self.db = db
        self.mega_admin_id = mega_admin_id
        self.broadcast = broadcast_manager
        self.admin_states = {}
        logger.info("👑 Advanced Admin Panel initialized")
    
    def is_admin(self, user_id: int) -> bool:
        return user_id == self.mega_admin_id or self.db.is_admin(user_id)
    
    def is_mega_admin(self, user_id: int) -> bool:
        return user_id == self.mega_admin_id
    
    async def show_admin_panel(self, update: Update, context) -> None:
        try:
            user_id = update.effective_user.id
            
            if not self.is_admin(user_id):
                return
            
            stats = self.db.get_statistics()
            banned_count = len(self.db.get_banned_users(page=1, per_page=1000)['users'])
            admin_count = len(self.db.get_admins())
            channel_count = len(self.db.get_mandatory_channels())
            
            message = f"""👑 BOSHQARUV PANELI

📊 Statistika:
• 👥 Foydalanuvchilar: {stats.get('total_users', 0)}
• 🟢 Bugun faol: {stats.get('active_today', 0)}
• 🔍 Qidiruvlar: {stats.get('total_searches', 0)}
• ⬇️ Yuklab olishlar: {stats.get('total_downloads', 0)}

⚙️ Tizim:
• 🚫 Bloklangan: {banned_count}
• 👑 Adminlar: {admin_count}
• 📢 Kanallar: {channel_count}"""
            
            keyboard = [
                [
                    InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="admin_users"),
                    InlineKeyboardButton("🚫 Ban boshqaruvi", callback_data="admin_ban")
                ],
                [
                    InlineKeyboardButton("📢 Majburiy azolik", callback_data="admin_subscription"),
                    InlineKeyboardButton("💎 Premium", callback_data="admin_premium")
                ],
                [
                    InlineKeyboardButton("👑 Adminlar", callback_data="admin_admins"),
                    InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")
                ],
                [
                    InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                    InlineKeyboardButton("⚙️ Sozlamalar", callback_data="admin_settings")
                ],
                [
                    InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if hasattr(update, 'callback_query') and update.callback_query:
                try:
                    await update.callback_query.edit_message_text(
                        message,
                        reply_markup=reply_markup
                    )
                except BadRequest as e:
                    if "message is not modified" in str(e).lower():
                        await update.callback_query.answer("Panel allaqachon ochiq")
                    else:
                        raise
            else:
                await update.message.reply_text(
                    message,
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            logger.error(f"Admin panel error: {e}")
    
    async def handle_callback(self, update: Update, context, data: str) -> None:
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            if not self.is_admin(user_id):
                await query.answer("❌ Ruxsat yo'q!", show_alert=True)
                return
            
            if data == "admin_panel":
                await self.show_admin_panel(update, context)
            
            elif data == "admin_users":
                await self._show_users_management(update, context)
            
            elif data == "admin_ban":
                await self._show_ban_management(update, context)
            
            elif data == "admin_subscription":
                await self._show_subscription_management(update, context)
            
            elif data == "admin_premium":
                await self._show_premium_management(update, context)
            
            elif data == "admin_admins":
                await self._show_admin_management(update, context)
            
            elif data == "admin_stats":
                await self._show_detailed_statistics(update, context)
            
            elif data == "admin_broadcast":
                await self.broadcast.start_broadcast_session(user_id, update, context)
            
            elif data == "admin_settings":
                await self._show_settings(update, context)
            
            elif data.startswith("users_"):
                await self._handle_users_callbacks(update, context, data)
            
            elif data.startswith("ban_"):
                await self._handle_ban_callbacks(update, context, data)
            
            elif data.startswith("sub_"):
                await self._handle_subscription_callbacks(update, context, data)
            
            elif data.startswith("premium_"):
                await self._handle_premium_callbacks(update, context, data)
            
            elif data.startswith("admins_"):
                await self._handle_admin_callbacks(update, context, data)
            
            elif data.startswith("settings_"):
                await self._handle_settings_callbacks(update, context, data)
            
        except Exception as e:
            logger.error(f"Admin callback error: {e}")
            try:
                await query.answer("❌ Xatolik yuz berdi!", show_alert=True)
            except:
                pass
    
    async def _show_users_management(self, update: Update, context) -> None:
        try:
            stats = self.db.get_statistics()
            banned_count = len(self.db.get_banned_users(page=1, per_page=1000)['users'])
            
            message = f"""👥 FOYDALANUVCHILAR BOSHQARUVI

📊 Umumiy ma'lumot:
• 👥 Jami foydalanuvchilar: {stats.get('total_users', 0)}
• 🟢 Bugun faol: {stats.get('active_today', 0)}
• 📅 Hafta faol: {stats.get('active_week', 0)}
• 📆 Oy faol: {stats.get('active_month', 0)}
• 🔴 Bloklangan: {banned_count}
• ✅ Faol: {stats.get('total_users', 0) - banned_count}

🛠️ Boshqaruv amalları:"""
            
            keyboard = [
                [
                    InlineKeyboardButton("📋 Barcha foydalanuvchilar", callback_data="users_list_1"),
                    InlineKeyboardButton("🟢 Faol foydalanuvchilar", callback_data="users_active_1")
                ],
                [
                    InlineKeyboardButton("🔴 Bloklangan foydalanuvchilar", callback_data="users_banned_1"),
                    InlineKeyboardButton("🚫 ID orqali bloklash", callback_data="users_ban_input")
                ],
                [
                    InlineKeyboardButton("✅ ID orqali blokdan chiqarish", callback_data="users_unban_input"),
                    InlineKeyboardButton("🔍 Foydalanuvchi qidirish", callback_data="users_search")
                ],
                [
                    InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")
                ]
            ]
            
            try:
                await update.callback_query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except BadRequest as e:
                if "message is not modified" in str(e).lower():
                    await update.callback_query.answer("Panel allaqachon ochiq")
                else:
                    raise
            
        except Exception as e:
            logger.error(f"Users management error: {e}")
    
    async def _handle_users_callbacks(self, update: Update, context, data: str) -> None:
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            if data.startswith("users_list_"):
                page = int(data.split("_")[2])
                await self._show_users_list(update, context, page, "all")
            
            elif data.startswith("users_active_"):
                page = int(data.split("_")[2])
                await self._show_users_list(update, context, page, "active")
            
            elif data.startswith("users_banned_"):
                page = int(data.split("_")[2])
                await self._show_banned_users_list(update, context, page)
            
            elif data == "users_ban_input":
                self.admin_states[user_id] = {'action': 'ban_user', 'step': 'waiting_id'}
                await query.answer("🚫 Ban qilish")
                await query.edit_message_text(
                    "🚫 Foydalanuvchini ban qilish\n\nFoydalanuvchi ID sini yuboring:"
                )
            
            elif data == "users_unban_input":
                self.admin_states[user_id] = {'action': 'unban_user', 'step': 'waiting_id'}
                await query.answer("✅ Unban qilish")
                await query.edit_message_text(
                    "✅ Foydalanuvchini unban qilish\n\nFoydalanuvchi ID sini yuboring:"
                )
            
        except Exception as e:
            logger.error(f"Users callback error: {e}")
    
    async def _show_users_list(self, update: Update, context, page: int, list_type: str) -> None:
        try:
            per_page = 5
            offset = (page - 1) * per_page
            
            if list_type == "all":
                users = self.db.get_all_users()
                title = "BARCHA FOYDALANUVCHILAR"
            else:
                users = self.db.get_all_users()
                title = "FAOL FOYDALANUVCHILAR"
            
            total = len(users)
            total_pages = (total + per_page - 1) // per_page
            page_users = users[offset:offset + per_page]
            
            if not page_users:
                await update.callback_query.edit_message_text(
                    "❌ Foydalanuvchilar topilmadi!"
                )
                return
            
            message = f"👥 {title}\n\n📄 Sahifa {page}/{total_pages} (Jami: {total})\n\n"
            
            for i, user in enumerate(page_users, start=offset + 1):
                name = user.get('first_name', 'N/A')
                username = f"@{user.get('username')}" if user.get('username') else "Username yo'q"
                user_id = user.get('user_id')
                
                message += f"{i}. {name}\n"
                message += f"   👤 {username}\n"
                message += f"   🆔 ID: {user_id}\n\n"
            
            keyboard = []
            nav_buttons = []
            
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ Orqaga", callback_data=f"users_{list_type}_{page-1}"))
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"users_{list_type}_{page+1}"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            keyboard.append([InlineKeyboardButton("🔙 Foydalanuvchilar", callback_data="admin_users")])
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"Users list error: {e}")
    
    async def _show_ban_management(self, update: Update, context) -> None:
        try:
            banned_data = self.db.get_banned_users(page=1, per_page=5)
            banned_users = banned_data['users']
            total_banned = banned_data['total']
            
            message = f"""🚫 BAN BOSHQARUVI

📊 Jami bloklangan: {total_banned}

Oxirgi bloklanganlar:"""
            
            for user in banned_users[:3]:
                name = user.get('first_name', 'N/A')
                username = f"@{user.get('username')}" if user.get('username') else "Username yo'q"
                reason = user.get('ban_reason', 'Sabab ko\'rsatilmagan')[:30]
                message += f"\n• {name} ({username})\n  Sabab: {reason}"
            
            keyboard = [
                [
                    InlineKeyboardButton("🚫 ID orqali ban", callback_data="ban_by_id"),
                    InlineKeyboardButton("✅ ID orqali unban", callback_data="ban_unban_id")
                ],
                [
                    InlineKeyboardButton("📋 Barcha banlar", callback_data="ban_list_all"),
                    InlineKeyboardButton("🔍 Ban qidirish", callback_data="ban_search")
                ],
                [
                    InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")
                ]
            ]
            
            try:
                await update.callback_query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except BadRequest as e:
                if "message is not modified" in str(e).lower():
                    await update.callback_query.answer("Panel allaqachon ochiq")
                else:
                    raise
            
        except Exception as e:
            logger.error(f"Ban management error: {e}")
    
    async def _handle_ban_callbacks(self, update: Update, context, data: str) -> None:
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            if data == "ban_by_id":
                self.admin_states[user_id] = {'action': 'ban_user', 'step': 'waiting_id'}
                await query.answer("🚫 Ban qilish")
                await query.edit_message_text(
                    "🚫 Foydalanuvchini ban qilish\n\nFoydalanuvchi ID sini yuboring:"
                )
            
            elif data == "ban_unban_id":
                self.admin_states[user_id] = {'action': 'unban_user', 'step': 'waiting_id'}
                await query.answer("✅ Unban qilish")
                await query.edit_message_text(
                    "✅ Foydalanuvchini unban qilish\n\nFoydalanuvchi ID sini yuboring:"
                )
            
            elif data == "ban_list_all":
                await self._show_banned_users_list(update, context, page=1)
            
            elif data.startswith("ban_page_"):
                page = int(data.split("_")[2])
                await self._show_banned_users_list(update, context, page)
            
        except Exception as e:
            logger.error(f"Ban callback error: {e}")
    
    async def _show_banned_users_list(self, update: Update, context, page: int = 1) -> None:
        try:
            banned_data = self.db.get_banned_users(page=page, per_page=5)
            banned_users = banned_data['users']
            total = banned_data['total']
            total_pages = banned_data['total_pages']
            
            if not banned_users:
                await update.callback_query.edit_message_text(
                    "✅ Hech kim ban qilinmagan!"
                )
                return
            
            message = f"🚫 BLOKLANGAN FOYDALANUVCHILAR\n\n📄 Sahifa {page}/{total_pages} (Jami: {total})\n\n"
            
            for user in banned_users:
                name = user.get('first_name', 'N/A')
                username = f"@{user.get('username')}" if user.get('username') else "Username yo'q"
                user_id = user.get('user_id')
                reason = user.get('ban_reason', 'Sabab ko\'rsatilmagan')[:50]
                ban_date = user.get('ban_date', 'N/A')[:10]
                
                message += f"👤 {name}\n"
                message += f"🆔 ID: {user_id}\n"
                message += f"👤 Username: {username}\n"
                message += f"📝 Sabab: {reason}\n"
                message += f"📅 Sana: {ban_date}\n\n"
            
            keyboard = []
            nav_buttons = []
            
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ Orqaga", callback_data=f"ban_page_{page-1}"))
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"ban_page_{page+1}"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            keyboard.append([InlineKeyboardButton("🔙 Ban boshqaruvi", callback_data="admin_ban")])
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"Banned users list error: {e}")
    
    async def _show_subscription_management(self, update: Update, context) -> None:
        try:
            from subscription import SubscriptionManager
            
            subscription = context.bot_data.get('subscription')
            if not subscription:
                subscription = SubscriptionManager(self.db)
            
            channels = self.db.get_mandatory_channels()
            check_mode = subscription.get_check_mode()
            check_mode_text = subscription.get_check_mode_text()
            
            message = f"""📢 MAJBURIY AZOLIK BOSHQARUVI

⚙️ Joriy rejim: {check_mode_text}
📊 Majburiy kanallar: {len(channels)}

Tekshirish rejimlari:
• 🟢 Rejim 1: Faqat /start da tekshirish
• 🟡 Rejim 2: Har xabarda tekshirish  
• 🔴 Rejim 3: Har amalda tekshirish

Majburiy kanallar:"""
            
            for i, channel in enumerate(channels[:3], 1):
                title = channel.get('title', 'N/A')
                username = channel.get('username', 'N/A')
                message += f"\n{i}. {title} ({username})"
            
            keyboard = [
                [
                    InlineKeyboardButton("⚙️ Rejimni o'zgartirish", callback_data="sub_change_mode"),
                    InlineKeyboardButton("📢 Kanal qo'shish", callback_data="sub_add_channel")
                ],
                [
                    InlineKeyboardButton("📋 Barcha kanallar", callback_data="sub_list_channels"),
                    InlineKeyboardButton("🗑️ Kanal o'chirish", callback_data="sub_remove_channel")
                ],
                [
                    InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")
                ]
            ]
            
            try:
                await update.callback_query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except BadRequest as e:
                if "message is not modified" in str(e).lower():
                    await update.callback_query.answer("Panel allaqachon ochiq")
                else:
                    raise
            
        except Exception as e:
            logger.error(f"Subscription management error: {e}")
    
    async def _handle_subscription_callbacks(self, update: Update, context, data: str) -> None:
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            if data == "sub_change_mode":
                await self._show_subscription_mode_selection(update, context)
            
            elif data.startswith("sub_mode_"):
                mode = int(data.split("_")[2])
                from subscription import SubscriptionManager
                subscription = SubscriptionManager(self.db)
                
                if subscription.set_check_mode(mode, user_id):
                    mode_text = subscription.get_check_mode_text()
                    await query.answer(f"✅ Rejim o'zgartirildi: {mode_text}")
                    await self._show_subscription_management(update, context)
                else:
                    await query.answer("❌ Rejim o'zgartirishda xatolik!", show_alert=True)
            
            elif data == "sub_add_channel":
                self.admin_states[user_id] = {'action': 'add_channel', 'step': 'waiting_username'}
                await query.answer("📢 Kanal qo'shish")
                await query.edit_message_text(
                    "📢 Majburiy kanal qo'shish\n\nKanal username ini yuboring (@ bilan):\n\nMisol: @mychannel"
                )
            
            elif data == "sub_remove_channel":
                await self._show_channels_for_removal(update, context)
            
            elif data.startswith("sub_remove_"):
                channel_id = data.split("_", 2)[2]
                if self.db.remove_mandatory_channel(channel_id, user_id):
                    await query.answer("✅ Kanal o'chirildi!")
                    await self._show_subscription_management(update, context)
                else:
                    await query.answer("❌ Kanal o'chirishda xatolik!", show_alert=True)
            
            elif data == "sub_list_channels":
                await self._show_all_channels(update, context)
            
        except Exception as e:
            logger.error(f"Subscription callback error: {e}")
    
    async def _show_subscription_mode_selection(self, update: Update, context) -> None:
        try:
            message = """⚙️ MAJBURIY AZOLIK REJIMI

Rejimni tanlang:

🟢 Rejim 1: Faqat /start da tekshirish
• Foydalanuvchi botni ishga tushirganda tekshiriladi
• Eng kam yuklanish

🟡 Rejim 2: Har xabarda tekshirish
• Har xabar yuborganda tekshiriladi
• O'rtacha yuklanish

🔴 Rejim 3: Har amalda tekshirish
• Har qanday amal bajarishda tekshiriladi
• Eng ko'p yuklanish"""
            
            keyboard = [
                [InlineKeyboardButton("🟢 Rejim 1", callback_data="sub_mode_1")],
                [InlineKeyboardButton("🟡 Rejim 2", callback_data="sub_mode_2")],
                [InlineKeyboardButton("🔴 Rejim 3", callback_data="sub_mode_3")],
                [InlineKeyboardButton("🔙 Majburiy azolik", callback_data="admin_subscription")]
            ]
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"Subscription mode selection error: {e}")
    
    async def _show_channels_for_removal(self, update: Update, context) -> None:
        try:
            channels = self.db.get_mandatory_channels()
            
            if not channels:
                await update.callback_query.edit_message_text(
                    "❌ O'chiriladigan kanallar yo'q!"
                )
                return
            
            message = "🗑️ KANAL O'CHIRISH\n\nO'chiriladigan kanalni tanlang:\n\n"
            
            keyboard = []
            for channel in channels:
                title = channel['title'][:30]
                keyboard.append([InlineKeyboardButton(
                    f"🗑️ {title}",
                    callback_data=f"sub_remove_{channel['channel_id']}"
                )])
            
            keyboard.append([InlineKeyboardButton("🔙 Majburiy azolik", callback_data="admin_subscription")])
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"Channels for removal error: {e}")
    
    async def _show_all_channels(self, update: Update, context) -> None:
        try:
            channels = self.db.get_mandatory_channels()
            
            message = "📋 BARCHA MAJBURIY KANALLAR\n\n"
            
            if channels:
                for i, channel in enumerate(channels, 1):
                    message += f"{i}. {channel['title']}\n"
                    message += f"   👤 @{channel['username']}\n"
                    message += f"   🆔 {channel['channel_id']}\n"
                    message += f"   📅 {channel.get('added_at', 'Noma\'lum')[:10]}\n\n"
            else:
                message += "❌ Majburiy kanallar yo'q"
            
            keyboard = [[InlineKeyboardButton("🔙 Majburiy azolik", callback_data="admin_subscription")]]
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"All channels error: {e}")
    
    async def _show_premium_management(self, update: Update, context) -> None:
        try:
            user_id = update.effective_user.id
            
            if not self.is_mega_admin(user_id):
                await update.callback_query.answer("❌ Faqat bot egasi premium boshqara oladi!", show_alert=True)
                return
            
            from premium import PremiumManager
            premium = context.bot_data.get('premium')
            if not premium:
                premium = PremiumManager(self.db)
            
            is_enabled = premium.is_premium_mode_enabled()
            status_text = "🟢 Yoqilgan" if is_enabled else "🔴 O'chirilgan"
            
            message = f"""💎 PREMIUM BOSHQARUVI

📊 Joriy holat: {status_text}

Premium rejimi haqida:
• 🔴 O'chirilgan: 50MB fayl limiti
• 🟢 Yoqilgan: 2GB fayl limiti

Faqat bot egasi premium rejimini boshqara oladi!

⚠️ Diqqat: Premium rejimi barcha foydalanuvchilarga ta'sir qiladi."""
            
            keyboard = []
            
            if is_enabled:
                keyboard.append([InlineKeyboardButton("🔴 Premium o'chirish", callback_data="premium_disable")])
            else:
                keyboard.append([InlineKeyboardButton("🟢 Premium yoqish", callback_data="premium_enable")])
            
            keyboard.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])
            
            try:
                await update.callback_query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except BadRequest as e:
                if "message is not modified" in str(e).lower():
                    await update.callback_query.answer("Panel allaqachon ochiq")
                else:
                    raise
            
        except Exception as e:
            logger.error(f"Premium management error: {e}")
    
    async def _handle_premium_callbacks(self, update: Update, context, data: str) -> None:
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            if not self.is_mega_admin(user_id):
                await query.answer("❌ Faqat bot egasi premium boshqara oladi!", show_alert=True)
                return
            
            from premium import PremiumManager
            premium = PremiumManager(self.db)
            
            if data == "premium_enable":
                if premium.enable_premium_mode(user_id):
                    await query.answer("✅ Premium yoqildi!")
                    await self._show_premium_management(update, context)
                else:
                    await query.answer("❌ Premium yoqishda xatolik!", show_alert=True)
            
            elif data == "premium_disable":
                if premium.disable_premium_mode(user_id):
                    await query.answer("✅ Premium o'chirildi!")
                    await self._show_premium_management(update, context)
                else:
                    await query.answer("❌ Premium o'chirishda xatolik!", show_alert=True)
            
        except Exception as e:
            logger.error(f"Premium callback error: {e}")
    
    async def _show_admin_management(self, update: Update, context) -> None:
        try:
            user_id = update.effective_user.id
            
            if not self.is_mega_admin(user_id):
                await update.callback_query.answer("❌ Faqat bot egasi admin boshqara oladi!", show_alert=True)
                return
            
            admins = self.db.get_admins()
            
            message = f"""👑 ADMIN BOSHQARUVI

📊 Jami adminlar: {len(admins)}

Adminlar ro'yxati:"""
            
            for admin in admins[:5]:
                name = admin.get('first_name', 'N/A')
                username = f"@{admin.get('username')}" if admin.get('username') else "Username yo'q"
                admin_id = admin.get('user_id')
                message += f"\n• {name} ({username})\n  ID: {admin_id}"
            
            if len(admins) > 5:
                message += f"\n\n... va yana {len(admins) - 5} admin"
            
            keyboard = [
                [
                    InlineKeyboardButton("➕ Admin qo'shish", callback_data="admins_add"),
                    InlineKeyboardButton("➖ Admin o'chirish", callback_data="admins_remove")
                ],
                [
                    InlineKeyboardButton("📋 Barcha adminlar", callback_data="admins_list_all"),
                    InlineKeyboardButton("🔍 Admin qidirish", callback_data="admins_search")
                ],
                [
                    InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")
                ]
            ]
            
            try:
                await update.callback_query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except BadRequest as e:
                if "message is not modified" in str(e).lower():
                    await update.callback_query.answer("Panel allaqachon ochiq")
                else:
                    raise
            
        except Exception as e:
            logger.error(f"Admin management error: {e}")
    
    async def _handle_admin_callbacks(self, update: Update, context, data: str) -> None:
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            if not self.is_mega_admin(user_id):
                await query.answer("❌ Faqat bot egasi admin boshqara oladi!", show_alert=True)
                return
            
            if data == "admins_add":
                self.admin_states[user_id] = {'action': 'add_admin', 'step': 'waiting_id'}
                await query.answer("➕ Admin qo'shish")
                await query.edit_message_text(
                    "➕ Admin qo'shish\n\nYangi admin ID sini yuboring:"
                )
            
            elif data == "admins_remove":
                self.admin_states[user_id] = {'action': 'remove_admin', 'step': 'waiting_id'}
                await query.answer("➖ Admin o'chirish")
                await query.edit_message_text(
                    "➖ Admin o'chirish\n\nO'chiriladigan admin ID sini yuboring:"
                )
            
            elif data == "admins_list_all":
                await self._show_all_admins(update, context)
            
        except Exception as e:
            logger.error(f"Admin callback error: {e}")
    
    async def _show_all_admins(self, update: Update, context) -> None:
        try:
            admins = self.db.get_admins()
            
            message = "👑 BARCHA ADMINLAR\n\n"
            
            if admins:
                for i, admin in enumerate(admins, 1):
                    name = admin.get('first_name', 'N/A')
                    username = f"@{admin.get('username')}" if admin.get('username') else "Username yo'q"
                    admin_id = admin.get('user_id')
                    added_date = admin.get('added_at', 'Noma\'lum')[:10]
                    
                    message += f"{i}. {name}\n"
                    message += f"   👤 {username}\n"
                    message += f"   🆔 {admin_id}\n"
                    message += f"   📅 {added_date}\n\n"
            else:
                message += "❌ Adminlar yo'q"
            
            keyboard = [[InlineKeyboardButton("🔙 Admin boshqaruvi", callback_data="admin_admins")]]
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"All admins error: {e}")
    
    async def _show_detailed_statistics(self, update: Update, context) -> None:
        try:
            stats = self.db.get_statistics()
            
            current_message = f"""📊 BATAFSIL STATISTIKA

👥 Foydalanuvchilar:
• Jami: {stats.get('total_users', 0)}
• Bugun faol: {stats.get('active_today', 0)}
• Hafta faol: {stats.get('active_week', 0)}
• Oy faol: {stats.get('active_month', 0)}

📈 Faoliyat:
• Jami qidiruvlar: {stats.get('total_searches', 0)}
• Jami yuklab olishlar: {stats.get('total_downloads', 0)}
• Jami tanishlar: {stats.get('total_recognitions', 0)}

🎵 Platformalar:
• YouTube: {stats.get('youtube_downloads', 0)}
• Instagram: {stats.get('instagram_downloads', 0)}
• TikTok: {stats.get('tiktok_downloads', 0)}

📊 Boshqaruv:
• Adminlar: {len(self.db.get_admins())}
• Bloklangan: {len(self.db.get_banned_users(page=1, per_page=1000)['users'])}
• Majburiy kanallar: {len(self.db.get_mandatory_channels())}"""
            
            keyboard = [
                [
                    InlineKeyboardButton("📈 Kunlik statistika", callback_data="stats_daily"),
                    InlineKeyboardButton("📊 Haftalik statistika", callback_data="stats_weekly")
                ],
                [
                    InlineKeyboardButton("📋 Oylik statistika", callback_data="stats_monthly"),
                    InlineKeyboardButton("🔄 Yangilash", callback_data="admin_stats")
                ],
                [
                    InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")
                ]
            ]
            
            try:
                await update.callback_query.edit_message_text(
                    current_message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except BadRequest as e:
                if "message is not modified" in str(e).lower():
                    await update.callback_query.answer("Statistika yangilandi")
                else:
                    raise
            
        except Exception as e:
            logger.error(f"Statistics error: {e}")
    
    async def _show_settings(self, update: Update, context) -> None:
        try:
            from subscription import SubscriptionManager
            from premium import PremiumManager
            
            subscription = SubscriptionManager(self.db)
            premium = PremiumManager(self.db)
            
            check_mode_text = subscription.get_check_mode_text()
            premium_status = "🟢 Yoqilgan" if premium.is_premium_mode_enabled() else "🔴 O'chirilgan"
            
            message = f"""⚙️ BOT SOZLAMALARI

📊 Joriy sozlamalar:
• 📢 Majburiy azolik: {check_mode_text}
• 💎 Premium rejim: {premium_status}
• 📢 Majburiy kanallar: {len(self.db.get_mandatory_channels())}
• 👑 Adminlar: {len(self.db.get_admins())}
• 🚫 Bloklangan: {len(self.db.get_banned_users(page=1, per_page=1000)['users'])}

⚙️ Sozlamalarni boshqarish:"""
            
            keyboard = [
                [
                    InlineKeyboardButton("📢 Majburiy azolik", callback_data="admin_subscription"),
                    InlineKeyboardButton("💎 Premium", callback_data="admin_premium")
                ],
                [
                    InlineKeyboardButton("👑 Adminlar", callback_data="admin_admins"),
                    InlineKeyboardButton("🚫 Ban boshqaruvi", callback_data="admin_ban")
                ],
                [
                    InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
                    InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
                ],
                [
                    InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")
                ]
            ]
            
            try:
                await update.callback_query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except BadRequest as e:
                if "message is not modified" in str(e).lower():
                    await update.callback_query.answer("Panel allaqachon ochiq")
                else:
                    raise
            
        except Exception as e:
            logger.error(f"Bot settings error: {e}")
    
    async def _handle_settings_callbacks(self, update: Update, context, data: str) -> None:
        try:
            query = update.callback_query
            
            if data == "settings_refresh":
                await self._show_settings(update, context)
                await query.answer("🔄 Yangilandi!")
            
        except Exception as e:
            logger.error(f"Settings callback error: {e}")
    
    async def handle_admin_message(self, update: Update, context) -> None:
        try:
            user_id = update.effective_user.id
            
            if user_id not in self.admin_states:
                return
            
            state = self.admin_states[user_id]
            action = state.get('action')
            step = state.get('step')
            text = update.message.text.strip()
            
            if action == 'ban_user' and step == 'waiting_id':
                try:
                    ban_user_id = int(text)
                    user_info = self.db.get_user_info(ban_user_id)
                    
                    if user_info:
                        self.admin_states[user_id]['ban_user_id'] = ban_user_id
                        self.admin_states[user_id]['step'] = 'waiting_reason'
                        
                        name = user_info.get('first_name', 'N/A')
                        username = f"@{user_info.get('username')}" if user_info.get('username') else "Username yo'q"
                        
                        await update.message.reply_text(
                            f"👤 Foydalanuvchi topildi:\n\n"
                            f"Ism: {name}\n"
                            f"Username: {username}\n"
                            f"ID: {ban_user_id}\n\n"
                            f"Ban sababini yozing:"
                        )
                    else:
                        await update.message.reply_text("❌ Foydalanuvchi topilmadi!")
                        del self.admin_states[user_id]
                        
                except ValueError:
                    await update.message.reply_text("❌ Yaroqsiz ID! Raqam kiriting.")
            
            elif action == 'ban_user' and step == 'waiting_reason':
                ban_user_id = state.get('ban_user_id')
                reason = text
                
                if self.db.ban_user(ban_user_id, reason, user_id):
                    await update.message.reply_text(
                        f"✅ Foydalanuvchi ban qilindi!\n\n"
                        f"ID: {ban_user_id}\n"
                        f"Sabab: {reason}"
                    )
                else:
                    await update.message.reply_text("❌ Ban qilishda xatolik!")
                
                del self.admin_states[user_id]
            
            elif action == 'unban_user' and step == 'waiting_id':
                try:
                    unban_user_id = int(text)
                    
                    if self.db.is_user_banned(unban_user_id):
                        if self.db.unban_user(unban_user_id, user_id):
                            await update.message.reply_text(
                                f"✅ Foydalanuvchi unban qilindi!\n\nID: {unban_user_id}"
                            )
                        else:
                            await update.message.reply_text("❌ Unban qilishda xatolik!")
                    else:
                        await update.message.reply_text("❌ Bu foydalanuvchi ban qilinmagan!")
                    
                    del self.admin_states[user_id]
                    
                except ValueError:
                    await update.message.reply_text("❌ Yaroqsiz ID! Raqam kiriting.")
            
            elif action == 'add_channel' and step == 'waiting_username':
                if text.startswith('@'):
                    username = text
                    channel_id = text
                    
                    try:
                        chat = await context.bot.get_chat(username)
                        title = chat.title
                        
                        if self.db.add_mandatory_channel(channel_id, username, title, user_id):
                            await update.message.reply_text(
                                f"✅ Kanal qo'shildi!\n\n"
                                f"Nomi: {title}\n"
                                f"Username: {username}"
                            )
                        else:
                            await update.message.reply_text("❌ Kanal qo'shishda xatolik!")
                    
                    except Exception as e:
                        await update.message.reply_text(f"❌ Kanal topilmadi yoki bot admin emas!\n\nXatolik: {str(e)}")
                    
                    del self.admin_states[user_id]
                else:
                    await update.message.reply_text("❌ Username @ bilan boshlanishi kerak!\n\nMisol: @mychannel")
            
            elif action == 'add_admin' and step == 'waiting_id':
                try:
                    new_admin_id = int(text)
                    
                    if new_admin_id == self.mega_admin_id:
                        await update.message.reply_text("❌ Bot egasini admin qilib bo'lmaydi!")
                    elif self.db.is_admin(new_admin_id):
                        await update.message.reply_text("❌ Bu foydalanuvchi allaqachon admin!")
                    else:
                        if self.db.add_admin(new_admin_id, user_id):
                            await update.message.reply_text(
                                f"✅ Yangi admin qo'shildi!\n\nID: {new_admin_id}"
                            )
                        else:
                            await update.message.reply_text("❌ Admin qo'shishda xatolik!")
                    
                    del self.admin_states[user_id]
                    
                except ValueError:
                    await update.message.reply_text("❌ Yaroqsiz ID! Raqam kiriting.")
            
            elif action == 'remove_admin' and step == 'waiting_id':
                try:
                    remove_admin_id = int(text)
                    
                    if remove_admin_id == self.mega_admin_id:
                        await update.message.reply_text("❌ Bot egasini admin ro'yxatidan chiqarib bo'lmaydi!")
                    elif not self.db.is_admin(remove_admin_id):
                        await update.message.reply_text("❌ Bu foydalanuvchi admin emas!")
                    else:
                        if self.db.remove_admin(remove_admin_id, user_id):
                            await update.message.reply_text(
                                f"✅ Admin o'chirildi!\n\nID: {remove_admin_id}"
                            )
                        else:
                            await update.message.reply_text("❌ Admin o'chirishda xatolik!")
                    
                    del self.admin_states[user_id]
                    
                except ValueError:
                    await update.message.reply_text("❌ Yaroqsiz ID! Raqam kiriting.")
            
        except Exception as e:
            logger.error(f"Admin message handling error: {e}")
            if user_id in self.admin_states:
                del self.admin_states[user_id]
            await update.message.reply_text("❌ Xatolik yuz berdi!")
