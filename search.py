import logging
import asyncio
import os
import tempfile
import requests
import json
import time
import uuid
from typing import Dict, List, Any, Optional
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger(__name__)

class FastMusicSearcher:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="search")
        self.search_cache = {}
        self.cache_lock = threading.Lock()
        self.cache_ttl = 300
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.ytdown_api = "https://ytdown.io/proxy.php"
        logger.info("🔍 Fast Music Searcher initialized")
    
    def clean_filename(self, title: str) -> str:
        import re
        return re.sub(r'[<>:"/\\|?*]', '', title)[:100]
    
    def _cleanup_cache(self):
        current_time = time.time()
        with self.cache_lock:
            expired_keys = [k for k, v in self.search_cache.items() 
                          if current_time - v['timestamp'] > self.cache_ttl]
            for key in expired_keys:
                del self.search_cache[key]
    
    async def search_music_fast(self, query: str, limit: int = 30) -> List[Dict[str, Any]]:
        try:
            self._cleanup_cache()
            
            cache_key = f"{query.lower().strip()}_{limit}"
            with self.cache_lock:
                if cache_key in self.search_cache:
                    cached_data = self.search_cache[cache_key]
                    if time.time() - cached_data['timestamp'] < self.cache_ttl:
                        return cached_data['results']
            
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                self.executor,
                self._search_sync,
                query,
                limit
            )
            
            with self.cache_lock:
                self.search_cache[cache_key] = {
                    'results': results,
                    'timestamp': time.time()
                }
            
            return results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def _search_sync(self, query: str, limit: int) -> List[Dict[str, Any]]:
        results = []
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'default_search': f'ytsearch{limit}:{query}',
            'ignoreerrors': True,
            'socket_timeout': 10,
            'retries': 2,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_results = ydl.extract_info(f'ytsearch{limit}:{query}', download=False)
                
                if search_results and 'entries' in search_results:
                    for entry in search_results['entries']:
                        if entry and entry.get('id'):
                            duration = entry.get('duration', 0)
                            if isinstance(duration, str):
                                try:
                                    duration = int(duration)
                                except:
                                    duration = 0
                            
                            view_count = entry.get('view_count', 0)
                            if not isinstance(view_count, int):
                                view_count = 0
                            
                            results.append({
                                'id': entry.get('id', ''),
                                'title': entry.get('title', 'Unknown'),
                                'artist': entry.get('uploader', 'Unknown'),
                                'url': f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                                'duration': duration,
                                'view_count': view_count,
                                'is_music': True
                            })
        
        except Exception as e:
            logger.error(f"Sync search error: {e}")
        
        return results
    
    async def download_song_background(self, song: Dict[str, Any], chat_id: int, context, user_lang: str, is_premium: bool, loading_message) -> None:
        try:
            await self._download_audio_only_async(
                song,
                chat_id,
                context,
                is_premium,
                loading_message
            )
        except Exception as e:
            logger.error(f"Download error: {e}")
            try:
                await loading_message.edit_text("❌ Yuklab olishda xatolik yuz berdi!")
            except:
                pass
    
    async def _download_audio_only_async(self, song: Dict[str, Any], chat_id: int, context, is_premium: bool, loading_message) -> None:
        try:
            url = song.get('url', '')
            title = self.clean_filename(song.get('title', 'Unknown'))
            
            # Update loading message
            try:
                await loading_message.edit_text(f"🎵 **Audio yuklanmoqda...**\n\n🎵 {song.get('title', 'Unknown')}\n👤 {song.get('artist', 'Unknown')}\n\n⏳ Biroz kuting...")
            except:
                pass
            
            # Get media info from API
            response = self.session.post(self.ytdown_api, data={"url": url}, timeout=15)
            response.raise_for_status()
            response_data = response.json()
            
            if not response_data.get("api") or response_data["api"].get("status") != "OK":
                raise Exception("API response error")
            
            api_data = response_data["api"]
            media_items = api_data.get("mediaItems", [])
            
            if not media_items:
                raise Exception("No media items found")
            
            # Find the best AUDIO format only
            best_audio = None
            
            # Priority: High quality M4A > Any M4A > Any audio format
            for item in media_items:
                media_type = item.get("type", "").lower()
                extension = item.get("mediaExtension", "").upper()
                quality = item.get("mediaQuality", "")
                
                # Only consider audio formats
                if media_type == "audio" or extension == "M4A":
                    # Skip bad quality formats
                    if "false" in quality.lower() or quality in ["48K"]:
                        continue
                    
                    # Prefer 128K quality
                    if quality == "128K":
                        best_audio = item
                        break
                    # If no 128K found, take any good M4A
                    elif not best_audio and extension == "M4A":
                        best_audio = item
            
            if not best_audio:
                # If no M4A found, try to find any audio format
                for item in media_items:
                    media_type = item.get("type", "").lower()
                    if media_type == "audio":
                        best_audio = item
                        break
            
            if not best_audio:
                raise Exception("No audio format found")
            
            media_url = best_audio.get("mediaUrl")
            if not media_url:
                raise Exception("No media URL found")
            
            # Check file size before downloading
            file_size_str = best_audio.get("mediaFileSize", "")
            max_size_mb = 50  # Always use 50MB limit for audio
            
            if file_size_str and file_size_str != "Unknown":
                try:
                    # Parse file size (e.g., "5.2 MB" -> 5.2)
                    size_parts = file_size_str.replace("MB", "").replace("GB", "000").strip()
                    file_size_mb = float(size_parts)
                    
                    if file_size_mb > max_size_mb:
                        await loading_message.edit_text(f"❌ Audio fayl juda katta ({file_size_mb:.1f}MB). Maksimal: {max_size_mb}MB")
                        return
                except:
                    pass  # Continue if we can't parse size
            
            # Get final download URL
            file_url, file_name = await self._get_detail_async(media_url)
            
            if not file_url or not file_name:
                raise Exception("Failed to get download URL")
            
            # Download the audio file
            temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(temp_dir, file_name)
            
            # Update loading message
            try:
                await loading_message.edit_text(f"📥 **Audio yuklanmoqda...**\n\n🎵 {song.get('title', 'Unknown')}\n👤 {song.get('artist', 'Unknown')}\n\n⏳ Deyarli tayyor...")
            except:
                pass
            
            download_response = self.session.get(file_url, stream=True, timeout=60)
            download_response.raise_for_status()
            
            # Check actual file size during download
            content_length = download_response.headers.get('content-length')
            if content_length:
                actual_size_mb = int(content_length) / (1024 * 1024)
                if actual_size_mb > max_size_mb:
                    await loading_message.edit_text(f"❌ Audio fayl juda katta ({actual_size_mb:.1f}MB). Maksimal: {max_size_mb}MB")
                    return
            
            with open(file_path, "wb") as f:
                downloaded_size = 0
                for chunk in download_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Check size during download
                        if downloaded_size > max_size_mb * 1024 * 1024:
                            f.close()
                            os.remove(file_path)
                            await loading_message.edit_text(f"❌ Audio fayl juda katta. Maksimal: {max_size_mb}MB")
                            return
            
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                # Delete loading message
                try:
                    await loading_message.delete()
                except:
                    pass
                
                # Send as audio
                with open(file_path, 'rb') as audio_file:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=audio_file,
                        title=song.get('title', 'Unknown'),
                        performer=song.get('artist', 'Unknown'),
                        caption=f"🎵 {song.get('title', 'Unknown')}\n👤 {song.get('artist', 'Unknown')}\n\n📱 @YourMusicBot orqali"
                    )
            else:
                await loading_message.edit_text("❌ Yuklab olingan fayl bo'sh!")
            
            # Cleanup
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
        except Exception as e:
            logger.error(f"Audio download error: {e}")
            try:
                if "413" in str(e) or "Entity Too Large" in str(e):
                    await loading_message.edit_text("❌ Fayl juda katta! Boshqa qo'shiqni sinab ko'ring.")
                elif "timeout" in str(e).lower():
                    await loading_message.edit_text("❌ Yuklab olish vaqti tugadi! Qayta urinib ko'ring.")
                else:
                    await loading_message.edit_text("❌ Audio yuklab olishda xatolik yuz berdi!")
            except:
                pass
            raise
    
    async def _get_detail_async(self, media_url: str) -> tuple:
        max_attempts = 10
        
        for attempt in range(max_attempts):
            try:
                response = self.session.post(self.ytdown_api, data={"url": media_url}, timeout=10)
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
                logger.error(f"_get_detail attempt {attempt + 1} error: {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)
                else:
                    break
        
        return None, None
