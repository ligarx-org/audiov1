import subprocess
import os
import json
import tempfile
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional
import requests
import time

logger = logging.getLogger(__name__)

class ShazamRecognizer:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="shazam")
        self.vibra_available = self._check_vibra()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if self.vibra_available:
            logger.info("🎙️ vibra is available for audio recognition")
        else:
            logger.warning("⚠️ vibra not available, using fallback recognition")
    
    def _check_vibra(self) -> bool:
        try:
            result = subprocess.run(['which', 'vibra'], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    async def recognize_from_telegram(self, message, user_lang: str) -> Dict[str, Any]:
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                self._recognize_complete_sync,
                message,
                user_lang
            )
        except Exception as e:
            logger.error(f"Recognition error: {e}")
            return {
                "success": False,
                "track_info": {},
                "duration": 0,
                "error": str(e)
            }
    
    def _recognize_complete_sync(self, message, user_lang: str) -> Dict[str, Any]:
        temp_file = None
        try:
            temp_file = self._extract_file_url_and_download(message)
            if not temp_file:
                return {
                    "success": False,
                    "track_info": {},
                    "duration": 0,
                    "error": "Failed to download file"
                }
            
            if self.vibra_available:
                return self._recognize_with_vibra(temp_file)
            else:
                return self._recognize_fallback(temp_file)
                
        except Exception as e:
            logger.error(f"Complete sync recognition error: {e}")
            return {
                "success": False,
                "track_info": {},
                "duration": 0,
                "error": str(e)
            }
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
    
    def _extract_file_url_and_download(self, message) -> Optional[str]:
        try:
            if message.audio:
                file_obj = message.audio
                ext = '.mp3'
            elif message.video:
                file_obj = message.video
                ext = '.mp4'
            elif message.voice:
                file_obj = message.voice
                ext = '.ogg'
            else:
                return None
            
            file_id = file_obj.file_id
            bot_token = message.get_bot().token
            
            file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
            
            response = self.session.get(file_info_url, timeout=10)
            response.raise_for_status()
            
            file_data = response.json()
            if not file_data.get('ok'):
                return None
            
            file_path = file_data['result']['file_path']
            download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
            
            temp_file = tempfile.mktemp(suffix=ext)
            
            download_response = self.session.get(download_url, timeout=30, stream=True)
            download_response.raise_for_status()
            
            with open(temp_file, 'wb') as f:
                for chunk in download_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"Downloaded file for recognition: {temp_file}")
            return temp_file
            
        except Exception as e:
            logger.error(f"Error extracting and downloading file: {e}")
            return None
    
    def _recognize_with_vibra(self, audio_path: str) -> Dict[str, Any]:
        try:
            start_time = time.time()
            
            temp_json = tempfile.mktemp(suffix='.json')
            
            cmd = ['vibra', '--recognize', '--file', audio_path]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=25
            )
            
            duration = time.time() - start_time
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "track_info": {},
                    "duration": duration,
                    "error": f"vibra error: {result.stderr}"
                }
            
            if not result.stdout.strip():
                return {
                    "success": False,
                    "track_info": {},
                    "duration": duration,
                    "error": "No recognition result"
                }
            
            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "track_info": {},
                    "duration": duration,
                    "error": "Invalid JSON response"
                }
            
            if 'track' not in data:
                return {
                    "success": False,
                    "track_info": {},
                    "duration": duration,
                    "error": "No track found"
                }
            
            track = data['track']
            
            album = "Unknown"
            try:
                sections = track.get('sections', [])
                if sections and isinstance(sections, list) and len(sections) > 0:
                    metadata = sections[0].get('metadata', [])
                    if metadata and isinstance(metadata, list) and len(metadata) > 0:
                        album = metadata[0].get('text', 'Unknown')
            except:
                album = "Unknown"
            
            genre = "Unknown"
            try:
                genres = track.get('genres')
                if genres and isinstance(genres, dict):
                    genre = genres.get('primary', 'Unknown')
            except:
                genre = "Unknown"
            
            cover_url = ""
            try:
                images = track.get('images')
                if images and isinstance(images, dict):
                    cover_url = images.get('coverart', '')
            except:
                cover_url = ""
            
            share_url = ""
            try:
                share = track.get('share')
                if share and isinstance(share, dict):
                    share_url = share.get('href', '')
            except:
                share_url = ""
            
            return {
                "success": True,
                "track_info": {
                    "title": track.get('title', 'Unknown'),
                    "artist": track.get('subtitle', 'Unknown'),
                    "album": album,
                    "cover_url": cover_url,
                    "share_url": share_url,
                    "genre": genre
                },
                "duration": duration
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "track_info": {},
                "duration": 25,
                "error": "Recognition timeout"
            }
        except Exception as e:
            logger.error(f"Vibra recognition error: {e}")
            return {
                "success": False,
                "track_info": {},
                "duration": 0,
                "error": str(e)
            }
    
    def _recognize_fallback(self, audio_path: str) -> Dict[str, Any]:
        return {
            "success": False,
            "track_info": {},
            "duration": 0,
            "error": "Recognition service not available"
        }
