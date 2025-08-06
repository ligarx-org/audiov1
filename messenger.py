import requests
import os
import json
import uuid
import tempfile
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, urlencode, quote, unquote
from bs4 import BeautifulSoup
import threading
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import time
import re
import shutil
import asyncio

logger = logging.getLogger(__name__)

class MessengerDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.cache = {}
        self.cache_lock = threading.Lock()
        self.cache_ttl = timedelta(minutes=15) # Increased TTL to 15 minutes for better session stability
        
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        })
        
        self.yt_base_url = "https://ytdown.io"
        self.yt_proxy_url = f"{self.yt_base_url}/proxy.php"
        
        self.tt_api_endpoint = "https://lovetik.com/api/ajax/search"
        
        self.insta_base_url = "https://insta-save.net"
        self.insta_api_url = f"{self.insta_base_url}/content.php"
        
        logger.info("📱 Messenger Downloader initialized with extended session TTL")
    
    def is_valid_url(self, url: str) -> bool:
        try:
            result = urlparse(url)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except:
            return False
    
    def clean_filename(self, title: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', '', title)[:100]
    
    def clean_url(self, url: str) -> str:
        return url.rstrip("+/ \t\n")
    
    def normalize_youtube_url(self, url: str) -> str:
        shorts_pattern = r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([a-zA-Z0-9_-]+)"
        match = re.match(shorts_pattern, url)
        if match:
            video_id = match.group(1)
            return f"https://www.youtube.com/watch?v={video_id}"
        return url
    
    def get_temp_path(self, chat_id: int, session_id: str, filename: str) -> str:
        return os.path.join("temp", "messenger", str(chat_id), session_id, filename)
    
    def cleanup_temp_files(self, chat_id: int, session_id: str) -> None:
        temp_dir = os.path.join("temp", "messenger", str(chat_id), session_id)
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except:
            pass
    
    def store_in_cache(self, session_id: str, data: Dict[str, Any]) -> None:
        self.cleanup_expired_cache()
        with self.cache_lock:
            self.cache[session_id] = {
                "data": data,
                "expires_at": datetime.now() + self.cache_ttl
            }
            logger.info(f"Stored session {session_id} in cache for {self.cache_ttl.total_seconds()} seconds")
    
    def get_from_cache(self, session_id: str) -> Optional[Dict[str, Any]]:
        self.cleanup_expired_cache()
        with self.cache_lock:
            cache_entry = self.cache.get(session_id)
            if cache_entry and datetime.now() <= cache_entry["expires_at"]:
                logger.info(f"Retrieved session {session_id} from cache")
                return cache_entry["data"]
            elif cache_entry:
                logger.warning(f"Session {session_id} expired")
            else:
                logger.warning(f"Session {session_id} not found in cache")
        return None
    
    def cleanup_expired_cache(self) -> None:
        with self.cache_lock:
            expired = [key for key, data in self.cache.items() 
                      if datetime.now() > data["expires_at"]]
            for key in expired:
                del self.cache[key]
                logger.info(f"Cleaned up expired session {key}")
    
    async def handle_url(self, update, context, url: str, user_lang: str = 'uz') -> None:
        try:
            url = self.clean_url(url)
            
            if not self.is_valid_url(url):
                await update.message.reply_text("❌ Yaroqsiz havola!")
                return
            
            if "youtube.com" in url.lower() or "youtu.be" in url.lower():
                await self.youtube_download(update, context, url)
            elif "tiktok.com" in url.lower():
                await self.tiktok_download(update, context, url)
            elif "instagram.com" in url.lower():
                await self.instagram_download(update, context, url)
            else:
                await update.message.reply_text("❌ Qo'llab-quvvatlanmaydigan platforma!")
                
        except Exception as e:
            logger.error(f"URL handling error: {e}")
            await update.message.reply_text("❌ Xatolik yuz berdi!")

    async def youtube_download(self, update, context, video_url: str) -> None:
        video_url = self.normalize_youtube_url(video_url)
        session_id = str(uuid.uuid4())
        chat_id = update.effective_chat.id
        
        loading_message = await update.message.reply_text("⏳ YouTube ishlanmoqda...")
        
        try:
            self.session.headers.update({
                "Origin": self.yt_base_url,
                "Referer": f"{self.yt_base_url}/en",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest"
            })
            
            response = self.session.post(self.yt_proxy_url, data={"url": video_url}, timeout=15)
            response.raise_for_status()
            api_data = response.json()
            
            if not api_data.get("api") or api_data["api"].get("status") != "OK":
                await loading_message.edit_text("❌ Video ma'lumotlarini olishda xatolik!")
                return
            
            api_data = api_data["api"]
            title = self.clean_filename(api_data.get("title", "YouTube Video"))
            thumbnail = api_data.get("imagePreviewUrl", "")
            media_items = api_data.get("mediaItems", [])
            
            # Filter out unwanted M4A formats
            formats = []
            for item in media_items:
                extension = item.get("mediaExtension", "").lower()
                quality = item.get("mediaQuality", "")
                
                # Skip unwanted M4A formats
                if extension == "m4a" and ("false" in quality.lower() or quality in ["48K", "128K"]):
                    continue
                
                if extension in ["mp4", "m4a"] and item.get("mediaUrl"):
                    formats.append({
                        "extension": item["mediaExtension"],
                        "resolution": item.get("mediaRes", ""),
                        "quality": item.get("mediaQuality", ""),
                        "url": item["mediaUrl"],
                        "file_size": item.get("mediaFileSize", ""),
                        "type": item.get("type", "")
                    })
            
            if not formats:
                await loading_message.edit_text("❌ Yuklab olish formatlar topilmadi!")
                return
            
            message = f"📹 **{title}**\n\n📋 **Formatlar:**\n"
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            keyboard = []
            
            for i, fmt in enumerate(formats, 1):
                format_name = f"{fmt['extension'].upper()} - {fmt['resolution']} {fmt['quality']}"
                message += f"{i}. {format_name} ({fmt['file_size'] or 'Noma\'lum'})\n"
                keyboard.append([InlineKeyboardButton(
                    format_name,
                    callback_data=f"yt_{i}_{timestamp}_{session_id}"
                )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            cache_data = {
                "yt_formats": formats,
                "yt_title": title,
                "yt_timestamp": timestamp
            }
            self.store_in_cache(session_id, cache_data)
            
            if thumbnail:
                thumb_filename = self.get_temp_path(chat_id, session_id, f"youtube_thumbnail_{timestamp}.jpg")
                if await self.download_file(thumbnail, thumb_filename, 0, update, context):
                    await loading_message.delete()
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=open(thumb_filename, "rb"),
                        caption=message,
                        parse_mode="Markdown",
                        reply_markup=reply_markup
                    )
                else:
                    await loading_message.edit_text(message, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                await loading_message.edit_text(message, parse_mode="Markdown", reply_markup=reply_markup)
        
        except Exception as e:
            logger.error(f"YouTube download error: {e}")
            await loading_message.edit_text("❌ YouTube dan yuklab olishda xatolik!")
        finally:
            self.cleanup_temp_files(chat_id, session_id)

    async def tiktok_download(self, update, context, video_url: str) -> None:
        session_id = str(uuid.uuid4())
        chat_id = update.effective_chat.id
        loading_message = await update.message.reply_text("⏳ TikTok ishlanmoqda...")
        
        try:
            headers = {
                "accept": "*/*",
                "accept-encoding": "gzip, deflate, br, zstd",
                "accept-language": "ru,en-US;q=0.9,en;q=0.8,uz;q=0.7",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "origin": "https://lovetik.com",
                "referer": "https://lovetik.com/",
                "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
                ),
                "x-requested-with": "XMLHttpRequest"
            }
            
            payload = {"query": video_url}
            
            response = self.session.post(self.tt_api_endpoint, headers=headers, data=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "ok":
                await loading_message.edit_text(f"❌ Xatolik: {data.get('mess', 'Noma\'lum xatolik')}")
                return
            
            title = self.clean_filename(data.get("desc", "TikTok Video"))
            thumbnail = data.get("cover", "")
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            author = data.get("author_name", "Noma'lum")
            
            message = (
                f"📹 **{title}**\n"
                f"👤 **Muallif:** {author}\n"
                f"📝 **Tavsif:** {data.get('desc', 'Tavsif yo\'q')}\n\n"
                f"📋 **Formatlar:**\n"
            )
            
            keyboard = []
            links = data.get('links', [])
            
            for i, link in enumerate(links, 1):
                link_type = link.get('t', 'N/A')
                quality = link.get('s', 'N/A')
                
                if 'MP4' in link_type:
                    format_name = f"📹 MP4 - {quality}"
                    message += f"{i}. {format_name}\n"
                    keyboard.append([InlineKeyboardButton(
                        format_name,
                        callback_data=f"tt_mp4_{i}_{timestamp}_{session_id}"
                    )])
                elif 'MP3' in link_type:
                    format_name = "🎵 MP3 Audio"
                    message += f"{i}. {format_name}\n"
                    keyboard.append([InlineKeyboardButton(
                        format_name,
                        callback_data=f"tt_mp3_{i}_{timestamp}_{session_id}"
                    )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            cache_data = {
                "tt_title": title,
                "tt_links": links,
                "tt_timestamp": timestamp
            }
            self.store_in_cache(session_id, cache_data)
            
            if thumbnail:
                thumb_filename = self.get_temp_path(chat_id, session_id, f"tiktok_thumbnail_{timestamp}.jpg")
                if await self.download_file(thumbnail, thumb_filename, 0, update, context):
                    await loading_message.delete()
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=open(thumb_filename, "rb"),
                        caption=message,
                        parse_mode="Markdown",
                        reply_markup=reply_markup
                    )
                else:
                    await loading_message.edit_text(message, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                await loading_message.edit_text(message, parse_mode="Markdown", reply_markup=reply_markup)
        
        except Exception as e:
            logger.error(f"TikTok download error: {e}")
            await loading_message.edit_text("❌ TikTok dan yuklab olishda xatolik!")
        finally:
            self.cleanup_temp_files(chat_id, session_id)

    async def instagram_download(self, update, context, url: str) -> None:
        session_id = str(uuid.uuid4())
        chat_id = update.effective_chat.id
        loading_message = await update.message.reply_text("⏳ Instagram ishlanmoqda...")
        
        try:
            self.session.headers.update({
                "Origin": self.insta_base_url,
                "Referer": f"{self.insta_base_url}/",
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest"
            })
            
            params = {"url": url}
            query_string = urlencode(params, quote_via=quote)
            full_url = f"{self.insta_api_url}?{query_string}"
            
            response = self.session.get(full_url, timeout=12)
            response.raise_for_status()
            api_data = response.json()
            
            if api_data.get("status") == "error":
                await loading_message.edit_text(f"❌ API Xatolik: {api_data.get('msg', 'Noma\'lum xatolik')}")
                return
            
            username = api_data.get("username", "")
            html_content = api_data.get("html", "")
            media_items, thumbnail, caption = self.parse_media_from_html(html_content)
            
            if not media_items:
                await loading_message.edit_text("❌ Yuklab olish uchun media topilmadi!")
                return
            
            selected = media_items[0]
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            display_name = self.clean_filename(caption if caption else username if username else "Instagram Media")
            
            message = (
                f"📹 **{display_name}**\n"
                f"👤 **Foydalanuvchi:** {username or 'Noma\'lum'}\n"
                f"📝 **Izoh:** {caption or 'Izoh yo\'q'}\n\n"
                f"📋 **Formatlar:**\n"
                f"1. Asl MP4\n"
                f"2. Audio MP3"
            )
            
            keyboard = [
                [InlineKeyboardButton("📹 MP4", callback_data=f"insta_mp4_{timestamp}_{session_id}")],
                [InlineKeyboardButton("🎵 MP3", callback_data=f"insta_mp3_{timestamp}_{session_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            cache_data = {
                "insta_title": display_name,
                "insta_url": selected["url"],
                "insta_direct_url": selected["direct_url"],
                "insta_timestamp": timestamp
            }
            self.store_in_cache(session_id, cache_data)
            
            if thumbnail:
                thumb_filename = self.get_temp_path(chat_id, session_id, f"insta_thumbnail_{timestamp}.jpg")
                direct_thumb_url = unquote(thumbnail.split("media.php?media=")[1]) if "media.php?media=" in thumbnail else thumbnail
                if await self.download_file(thumbnail, thumb_filename, 0, update, context, direct_thumb_url):
                    await loading_message.delete()
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=open(thumb_filename, "rb"),
                        caption=message,
                        parse_mode="Markdown",
                        reply_markup=reply_markup
                    )
                else:
                    await loading_message.edit_text(message, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                await loading_message.edit_text(message, parse_mode="Markdown", reply_markup=reply_markup)
        
        except Exception as e:
            logger.error(f"Instagram download error: {e}")
            await loading_message.edit_text("❌ Instagram dan yuklab olishda xatolik!")
        finally:
            self.cleanup_temp_files(chat_id, session_id)

    def parse_media_from_html(self, html_content: str) -> tuple:
        soup = BeautifulSoup(html_content, "html.parser")
        media_items = []
        
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "media.php?media=" in href:
                title_tag = link.find("span", class_="d-block")
                title = self.clean_filename(link.get("title", "") or (title_tag.text.strip() if title_tag else "Instagram Media"))
                file_size = link.get("data-filesize", "Noma'lum")
                name = link.get("name", "")
                extension = name.split(".")[-1].lower() if name and "." in name else "mp4"
                direct_url = unquote(href.split("media.php?media=")[1]) if "media.php?media=" in href else href
                
                media_items.append({
                    "url": href,
                    "direct_url": direct_url,
                    "title": title,
                    "file_size": file_size,
                    "extension": extension,
                    "name": name
                })
        
        video = soup.find("video")
        thumbnail = video.get("poster") if video and video.get("poster") else None
        
        caption_tag = soup.find("p", class_="text-sm", style="word-break: break-word; max-width: 100%;")
        caption = caption_tag.text.strip() if caption_tag else ""
        
        return media_items, thumbnail, caption

    async def download_file(self, url: str, filename: str, file_size: float, update=None, context=None, direct_url: Optional[str] = None) -> bool:
        try:
            response = self.session.get(url, stream=True, timeout=20)
            
            if response.status_code != 200 and direct_url:
                response = self.session.get(direct_url, stream=True, timeout=20)
            
            if response.status_code != 200:
                logger.error(f"Download failed: HTTP {response.status_code}")
                return False
            
            content_type = response.headers.get("content-type", "").lower()
            is_valid = any(ct in content_type for ct in ["image/", "video/", "application/octet-stream"])
            
            if not is_valid:
                logger.error(f"Invalid content type: {content_type}")
                return False
            
            total_size = int(response.headers.get("content-length", file_size * 1024 * 1024))
            max_size = 100 # Increased from 50MB to 100MB for general downloads
            if total_size > max_size * 1024 * 1024:
                logger.error(f"File too large: {total_size / (1024 * 1024):.2f} MB")
                return False
            
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            with open(filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"Download completed: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return False

    async def convert_to_mp3(self, input_path: str, mp3_path: str) -> bool:
        try:
            from pydub import AudioSegment
            os.makedirs(os.path.dirname(mp3_path), exist_ok=True)
            audio = AudioSegment.from_file(input_path)
            audio.export(mp3_path, format="mp3", bitrate="192k")
            return True
        except Exception as e:
            logger.error(f"Error converting to MP3: {e}")
            return False

    async def handle_callback(self, update, context, data: str, user_lang: str = 'uz') -> None:
        parts = data.split("_")
        if len(parts) < 3:
            await update.callback_query.answer("❌ Yaroqsiz tugma ma'lumoti!", show_alert=True)
            return
        
        platform = parts[0]
        format_type = parts[1]
        
        # Handle variable number of parts for different platforms
        if len(parts) >= 4:
            timestamp = parts[2]
            session_id = parts[3]
        else:
            await update.callback_query.answer("❌ Yaroqsiz tugma ma'lumoti!", show_alert=True)
            return
        
        cache_data = self.get_from_cache(session_id)
        
        if not cache_data:
            await update.callback_query.answer("❌ Sessiya tugadi. Havolani qayta yuboring!", show_alert=True)
            return
        
        await update.callback_query.answer(f"✅ {format_type.upper()} format yuklanmoqda...")
        
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        try:
            if platform == "yt":
                await self._handle_youtube_callback(update, context, format_type, timestamp, session_id, cache_data, chat_id, user_id)
            elif platform == "tt":
                await self._handle_tiktok_callback(update, context, format_type, timestamp, session_id, cache_data, chat_id, user_id)
            elif platform == "insta":
                await self._handle_instagram_callback(update, context, format_type, timestamp, session_id, cache_data, chat_id, user_id)
        
        except Exception as e:
            logger.error(f"Error in callback handler: {e}")
            await context.bot.send_message(chat_id=chat_id, text="❌ Yuklab olishda xatolik yuz berdi!")
        finally:
            self.cleanup_temp_files(chat_id, session_id)

    async def _handle_youtube_callback(self, update, context, format_type, timestamp, session_id, cache_data, chat_id, user_id):
        try:
            index = int(format_type) - 1
            formats = cache_data.get("yt_formats", [])
            title = cache_data.get("yt_title", "YouTube Video")
            
            if index >= len(formats):
                await context.bot.send_message(chat_id=chat_id, text="❌ Yaroqsiz format tanlandi!")
                return
            
            selected = formats[index]
            extension = selected["extension"]
            filename = self.get_temp_path(chat_id, session_id, f"youtube_media_{timestamp}.{extension}")
            
            file_url, file_name = await self._get_final_download_url(selected["url"])
            if not file_url:
                await context.bot.send_message(chat_id=chat_id, text="❌ Yuklab olish havolasini olishda xatolik!")
                return
            
            if await self.download_file(file_url, filename, 0, update, context):
                if os.path.exists(filename) and os.path.getsize(filename) > 0:
                    with open(filename, "rb") as f:
                        if extension.lower() == "mp4":
                            await context.bot.send_video(
                                chat_id=chat_id,
                                video=f,
                                caption=f"📹 **{title}**\n🎬 YouTube dan yuklab olindi",
                                supports_streaming=True
                            )
                        else:
                            await context.bot.send_audio(
                                chat_id=chat_id,
                                audio=f,
                                title=title,
                                caption=f"🎵 **{title}**\n🎬 YouTube dan yuklab olindi"
                            )
                    # Log successful download
                    if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                        asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                            user_id, 'download', {'title': title, 'format': extension, 'platform': 'youtube'}, platform='youtube', success=True
                        ))
                else:
                    await context.bot.send_message(chat_id=chat_id, text="❌ Yuklab olingandan keyin fayl topilmadi!")
                    if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                        asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                            user_id, 'download', {'title': title, 'format': extension, 'platform': 'youtube', 'error': 'Empty file'}, platform='youtube', success=False
                        ))
            else:
                await context.bot.send_message(chat_id=chat_id, text="❌ Video yuklab olishda xatolik!")
                if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                    asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                        user_id, 'download', {'title': title, 'format': extension, 'platform': 'youtube', 'error': 'Download failed'}, platform='youtube', success=False
                    ))
        except Exception as e:
            logger.error(f"YouTube callback error: {e}")
            await context.bot.send_message(chat_id=chat_id, text="❌ Yuklab olishda xatolik yuz berdi!")
            if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                    user_id, 'download', {'title': title, 'platform': 'youtube', 'error': str(e)}, platform='youtube', success=False
                ))

    async def _handle_tiktok_callback(self, update, context, format_type, timestamp, session_id, cache_data, chat_id, user_id):
        try:
            title = cache_data.get("tt_title", "TikTok Video")
            links = cache_data.get("tt_links", [])
            
            # Parse the format type and index
            if format_type.startswith("mp4"):
                # Extract index from callback data like "tt_mp4_1_timestamp_session"
                parts = update.callback_query.data.split("_")
                if len(parts) >= 3:
                    try:
                        link_index = int(parts[2]) - 1
                    except (ValueError, IndexError):
                        link_index = 0
                else:
                    link_index = 0
                
                if link_index >= len(links):
                    await context.bot.send_message(chat_id=chat_id, text="❌ Yaroqsiz format tanlandi!")
                    return
                
                selected_link = links[link_index]
                download_url = selected_link.get("a", "")
                
                if not download_url:
                    await context.bot.send_message(chat_id=chat_id, text="❌ Yuklab olish havolasi topilmadi!")
                    return
                
                filename = self.get_temp_path(chat_id, session_id, f"tiktok_media_{timestamp}.mp4")
                
                if await self.download_file(download_url, filename, 0, update, context):
                    if os.path.exists(filename) and os.path.getsize(filename) > 0:
                        with open(filename, "rb") as f:
                            await context.bot.send_video(
                                chat_id=chat_id,
                                video=f,
                                caption=f"📹 **{title}**\n🎵 TikTok Video",
                                supports_streaming=True
                            )
                        # Log successful download
                        if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                            asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                                user_id, 'download', {'title': title, 'format': 'mp4', 'platform': 'tiktok'}, platform='tiktok', success=True
                            ))
                    else:
                        await context.bot.send_message(chat_id=chat_id, text="❌ Yuklab olingandan keyin fayl topilmadi!")
                        if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                            asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                                user_id, 'download', {'title': title, 'format': 'mp4', 'platform': 'tiktok', 'error': 'Empty file'}, platform='tiktok', success=False
                            ))
                else:
                    await context.bot.send_message(chat_id=chat_id, text="❌ Video yuklab olishda xatolik!")
                    if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                        asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                            user_id, 'download', {'title': title, 'format': 'mp4', 'platform': 'tiktok', 'error': 'Download failed'}, platform='tiktok', success=False
                        ))
            
            elif format_type.startswith("mp3"):
                # Extract index from callback data
                parts = update.callback_query.data.split("_")
                if len(parts) >= 3:
                    try:
                        link_index = int(parts[2]) - 1
                    except (ValueError, IndexError):
                        link_index = 0
                else:
                    link_index = 0
                
                if link_index >= len(links):
                    await context.bot.send_message(chat_id=chat_id, text="❌ Yaroqsiz format tanlandi!")
                    return
                
                selected_link = links[link_index]
                download_url = selected_link.get("a", "")
                
                if not download_url:
                    await context.bot.send_message(chat_id=chat_id, text="❌ Yuklab olish havolasi topilmadi!")
                    return
                
                if 'MP3' in selected_link.get('t', ''):
                    filename = self.get_temp_path(chat_id, session_id, f"tiktok_audio_{timestamp}.mp3")
                    
                    if await self.download_file(download_url, filename, 0, update, context):
                        if os.path.exists(filename) and os.path.getsize(filename) > 0:
                            with open(filename, "rb") as f:
                                await context.bot.send_audio(
                                    chat_id=chat_id,
                                    audio=f,
                                    title=title,
                                    caption=f"🎵 **{title}**\n🎵 TikTok Audio"
                                )
                            # Log successful download
                            if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                                asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                                    user_id, 'download', {'title': title, 'format': 'mp3', 'platform': 'tiktok'}, platform='tiktok', success=True
                                ))
                        else:
                            await context.bot.send_message(chat_id=chat_id, text="❌ MP3 fayl topilmadi!")
                            if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                                asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                                    user_id, 'download', {'title': title, 'format': 'mp3', 'platform': 'tiktok', 'error': 'Empty file'}, platform='tiktok', success=False
                                ))
                    else:
                        await context.bot.send_message(chat_id=chat_id, text="❌ Audio yuklab olishda xatolik!")
                        if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                            asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                                user_id, 'download', {'title': title, 'format': 'mp3', 'platform': 'tiktok', 'error': 'Download failed'}, platform='tiktok', success=False
                            ))
                else:
                    # Convert video to MP3
                    temp_mp4 = self.get_temp_path(chat_id, session_id, f"tiktok_temp_{timestamp}.mp4")
                    mp3_filename = self.get_temp_path(chat_id, session_id, f"tiktok_audio_{timestamp}.mp3")
                    
                    if await self.download_file(download_url, temp_mp4, 0, update, context):
                        if await self.convert_to_mp3(temp_mp4, mp3_filename):
                            if os.path.exists(mp3_filename) and os.path.getsize(mp3_filename) > 0:
                                with open(mp3_filename, "rb") as f:
                                    await context.bot.send_audio(
                                        chat_id=chat_id,
                                        audio=f,
                                        title=title,
                                        caption=f"🎵 **{title}**\n🎵 TikTok Audio"
                                    )
                                # Log successful download
                                if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                                    asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                                        user_id, 'download', {'title': title, 'format': 'mp3_converted', 'platform': 'tiktok'}, platform='tiktok', success=True
                                    ))
                            else:
                                await context.bot.send_message(chat_id=chat_id, text="❌ MP3 fayl topilmadi!")
                                if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                                    asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                                        user_id, 'download', {'title': title, 'format': 'mp3_converted', 'platform': 'tiktok', 'error': 'Empty converted file'}, platform='tiktok', success=False
                                    ))
                        else:
                            await context.bot.send_message(chat_id=chat_id, text="❌ MP3 ga o'tkazishda xatolik!")
                            if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                                asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                                    user_id, 'download', {'title': title, 'format': 'mp3_converted', 'platform': 'tiktok', 'error': 'Conversion failed'}, platform='tiktok', success=False
                                ))
                    else:
                        await context.bot.send_message(chat_id=chat_id, text="❌ Video yuklab olishda xatolik!")
                        if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                            asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                                user_id, 'download', {'title': title, 'format': 'mp3_converted', 'platform': 'tiktok', 'error': 'Download failed'}, platform='tiktok', success=False
                            ))
        except Exception as e:
            logger.error(f"TikTok callback error: {e}")
            await context.bot.send_message(chat_id=chat_id, text="❌ Yuklab olishda xatolik yuz berdi!")
            if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                    user_id, 'download', {'title': title, 'platform': 'tiktok', 'error': str(e)}, platform='tiktok', success=False
                ))

    async def _handle_instagram_callback(self, update, context, format_type, timestamp, session_id, cache_data, chat_id, user_id):
        try:
            title = cache_data.get("insta_title", "Instagram Media")
            url = cache_data.get("insta_url")
            direct_url = cache_data.get("insta_direct_url")
            
            if format_type == "mp4":
                filename = self.get_temp_path(chat_id, session_id, f"insta_media_{timestamp}.mp4")
                
                if await self.download_file(url, filename, 0, update, context, direct_url):
                    if os.path.exists(filename) and os.path.getsize(filename) > 0:
                        with open(filename, "rb") as f:
                            await context.bot.send_video(
                                chat_id=chat_id,
                                video=f,
                                caption=f"📹 **{title}**\n📱 Instagram Video",
                                supports_streaming=True
                            )
                        # Log successful download
                        if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                            asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                                user_id, 'download', {'title': title, 'format': 'mp4', 'platform': 'instagram'}, platform='instagram', success=True
                            ))
                    else:
                        await context.bot.send_message(chat_id=chat_id, text="❌ Yuklab olingandan keyin fayl topilmadi!")
                        if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                            asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                                user_id, 'download', {'title': title, 'format': 'mp4', 'platform': 'instagram', 'error': 'Empty file'}, platform='instagram', success=False
                            ))
                else:
                    await context.bot.send_message(chat_id=chat_id, text="❌ Media yuklab olishda xatolik!")
                    if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                        asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                            user_id, 'download', {'title': title, 'format': 'mp4', 'platform': 'instagram', 'error': 'Download failed'}, platform='instagram', success=False
                        ))
            
            elif format_type == "mp3":
                temp_mp4 = self.get_temp_path(chat_id, session_id, f"insta_temp_{timestamp}.mp4")
                mp3_filename = self.get_temp_path(chat_id, session_id, f"insta_audio_{timestamp}.mp3")
                
                if await self.download_file(url, temp_mp4, 0, update, context, direct_url):
                    if await self.convert_to_mp3(temp_mp4, mp3_filename):
                        if os.path.exists(mp3_filename) and os.path.getsize(mp3_filename) > 0:
                            with open(mp3_filename, "rb") as f:
                                await context.bot.send_audio(
                                    chat_id=chat_id,
                                    audio=f,
                                    title=title,
                                    caption=f"🎵 **{title}**\n📱 Instagram Audio"
                                )
                            # Log successful download
                            if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                                asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                                    user_id, 'download', {'title': title, 'format': 'mp3_converted', 'platform': 'instagram'}, platform='instagram', success=True
                                ))
                        else:
                            await context.bot.send_message(chat_id=chat_id, text="❌ MP3 fayl topilmadi!")
                            if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                                asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                                    user_id, 'download', {'title': title, 'format': 'mp3_converted', 'platform': 'instagram', 'error': 'Empty converted file'}, platform='instagram', success=False
                                ))
                    else:
                        await context.bot.send_message(chat_id=chat_id, text="❌ MP3 ga o'tkazishda xatolik!")
                        if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                            asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                                user_id, 'download', {'title': title, 'format': 'mp3_converted', 'platform': 'instagram', 'error': 'Conversion failed'}, platform='instagram', success=False
                            ))
                else:
                    await context.bot.send_message(chat_id=chat_id, text="❌ Media yuklab olishda xatolik!")
                    if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                        asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                            user_id, 'download', {'title': title, 'format': 'mp3_converted', 'platform': 'instagram', 'error': 'Download failed'}, platform='instagram', success=False
                        ))
        except Exception as e:
            logger.error(f"Instagram callback error: {e}")
            await context.bot.send_message(chat_id=chat_id, text="❌ Yuklab olishda xatolik yuz berdi!")
            if hasattr(context.bot_data, 'bot_instance') and context.bot_data.get('bot_instance'):
                asyncio.create_task(context.bot_data['bot_instance']._log_activity_background(
                    user_id, 'download', {'title': title, 'platform': 'instagram', 'error': str(e)}, platform='instagram', success=False
                ))

    async def _get_final_download_url(self, media_url: str) -> tuple:
        max_attempts = 10
        
        for attempt in range(max_attempts):
            try:
                response = self.session.post(self.yt_proxy_url, data={"url": media_url}, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("api") and data["api"].get("percent") == "Completed":
                    file_url = data["api"].get("fileUrl")
                    file_name = data["api"].get("fileName")
                    if file_url and file_name:
                        return file_url, file_name
                
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"_get_final_download_url attempt {attempt + 1} error: {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)
                else:
                    break
        
        return None, None
