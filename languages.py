"""
Multi-language support system
"""

import re
from typing import Dict, Any

# Supported languages
LANGUAGES = {
    'uz': 'O\'zbek',
    'ru': 'Русский', 
    'en': 'English'
}

# Language texts
TEXTS = {
    'uz': {
        'select_language': '🌐 **Tilni tanlang:**',
        'language_selected': '✅ Til tanlandi!',
        'welcome_message': '🎵 **Salom {name}!**\n\n**Ultra-Fast Music Bot**ga xush kelibsiz!\n\n🚀 **Imkoniyatlar:**\n• 🔍 Tezkor musiqa qidirish\n• 🎙️ Audio tanib olish\n• 📱 Media yuklab olish\n\n⚡ **Barcha amallar tezkor!**',
        'search_music': '🔍 Musiqa qidirish',
        'recognize_song': '🎙️ Qo\'shiq tanish',
        'download_media': '📱 Media yuklab olish',
        'help': '❓ Yordam',
        'banned_message': '🚫 **Siz bloklangansiz!**\n\n📝 **Sabab:** {reason}\n📅 **Sana:** {date}',
        'mandatory_subscription': '📢 **Majburiy azolik**\n\nBotdan foydalanish uchun quyidagi kanallarga a\'zo bo\'ling:',
        'check_subscription': '📢 Kanalga a\'zo bo\'lish',
        'verify_subscription': '✅ A\'zolikni tekshirish',
        'recognizing_audio': '🎙️ **Audio tanilmoqda...**\n\n⏳ Biroz kuting...',
        'recognition_success': 'Musiqa tanildi!',
        'recognition_failed': 'Musiqa tanilmadi',
        'processing_youtube': '📺 **YouTube dan yuklab olish**\n\n⏳ Tayyorlanmoqda...',
        'processing_tiktok': '🎵 **TikTok dan yuklab olish**\n\n⏳ Tayyorlanmoqda...',
        'processing_instagram': '📸 **Instagram dan yuklab olish**\n\n⏳ Tayyorlanmoqda...',
        'retrying': '🔄 Qayta urinish ({attempt}/3)...',
        'youtube_error': '❌ YouTube dan yuklab olishda xatolik!',
        'tiktok_error': '❌ TikTok dan yuklab olishda xatolik!',
        'instagram_error': '❌ Instagram dan yuklab olishda xatolik: {error}',
        'no_formats': '❌ Yuklab olish formatlar topilmadi!',
        'youtube_formats': '📺 **YouTube: {title}**\n\n📋 **Formatlar:**\n',
        'tiktok_formats': '🎵 **TikTok Video**\n\n🎤 **Muallif:** {author}\n📝 **Tavsif:** {description}\n\n📋 **Formatlar:**',
        'instagram_formats': '📸 **Instagram Media**\n\n👤 **Foydalanuvchi:** {user}\n📝 **Tavsif:** {caption}\n\n📋 **Formatlar:**',
        'video_mp4': '📹 Video (MP4)',
        'audio_mp3': '🎵 Audio (MP3)',
        'unknown': 'Noma\'lum',
        'no_description': 'Tavsif yo\'q',
        'no_caption': 'Izoh yo\'q',
        'unknown_error': 'Noma\'lum xatolik',
        'no_media_found': 'Media topilmadi',
        'invalid_button': 'Yaroqsiz tugma!',
        'session_expired': 'Sessiya tugadi!',
        'downloading_format': '{format} yuklab olinyapti...',
        'invalid_format': 'Yaroqsiz format!',
        'url_fetch_error': 'URL olishda xatolik!',
        'file_not_found': 'Fayl topilmadi!',
        'download_failed': 'Yuklab olish muvaffaqiyatsiz!',
        'download_error': 'Yuklab olishda xatolik!',
        'youtube_download_caption': '📺 **YouTube:** {title}',
        'tiktok_download_caption': '🎵 **TikTok:** {title}',
        'tiktok_audio_caption': '🎵 **TikTok Audio:** {title}',
        'instagram_download_caption': '📸 **Instagram:** {title}',
        'instagram_audio_caption': '🎵 **Instagram Audio:** {title}',
        'mp3_not_found': 'MP3 fayl topilmadi!',
        'conversion_failed': 'Konvertatsiya muvaffaqiyatsiz!',
        'invalid_url': '❌ Yaroqsiz havola!'
    },
    'ru': {
        'select_language': '🌐 **Выберите язык:**',
        'language_selected': '✅ Язык выбран!',
        'welcome_message': '🎵 **Привет {name}!**\n\n**Добро пожаловать в Ultra-Fast Music Bot!**\n\n🚀 **Возможности:**\n• 🔍 Быстрый поиск музыки\n• 🎙️ Распознавание аудио\n• 📱 Скачивание медиа\n\n⚡ **Все операции быстрые!**',
        'search_music': '🔍 Поиск музыки',
        'recognize_song': '🎙️ Распознать песню',
        'download_media': '📱 Скачать медиа',
        'help': '❓ Помощь',
        'banned_message': '🚫 **Вы заблокированы!**\n\n📝 **Причина:** {reason}\n📅 **Дата:** {date}',
        'mandatory_subscription': '📢 **Обязательная подписка**\n\nДля использования бота подпишитесь на каналы:',
        'check_subscription': '📢 Подписаться на канал',
        'verify_subscription': '✅ Проверить подписку',
        'recognizing_audio': '🎙️ **Распознавание аудио...**\n\n⏳ Подождите...',
        'recognition_success': 'Музыка распознана!',
        'recognition_failed': 'Музыка не распознана',
        'processing_youtube': '📺 **Скачивание с YouTube**\n\n⏳ Подготовка...',
        'processing_tiktok': '🎵 **Скачивание с TikTok**\n\n⏳ Подготовка...',
        'processing_instagram': '📸 **Скачивание с Instagram**\n\n⏳ Подготовка...',
        'retrying': '🔄 Повтор ({attempt}/3)...',
        'youtube_error': '❌ Ошибка скачивания с YouTube!',
        'tiktok_error': '❌ Ошибка скачивания с TikTok!',
        'instagram_error': '❌ Ошибка скачивания с Instagram: {error}',
        'no_formats': '❌ Форматы для скачивания не найдены!',
        'youtube_formats': '📺 **YouTube: {title}**\n\n📋 **Форматы:**\n',
        'tiktok_formats': '🎵 **TikTok Видео**\n\n🎤 **Автор:** {author}\n📝 **Описание:** {description}\n\n📋 **Форматы:**',
        'instagram_formats': '📸 **Instagram Медиа**\n\n👤 **Пользователь:** {user}\n📝 **Описание:** {caption}\n\n📋 **Форматы:**',
        'video_mp4': '📹 Видео (MP4)',
        'audio_mp3': '🎵 Аудио (MP3)',
        'unknown': 'Неизвестно',
        'no_description': 'Нет описания',
        'no_caption': 'Нет подписи',
        'unknown_error': 'Неизвестная ошибка',
        'no_media_found': 'Медиа не найдено',
        'invalid_button': 'Неверная кнопка!',
        'session_expired': 'Сессия истекла!',
        'downloading_format': 'Скачивается {format}...',
        'invalid_format': 'Неверный формат!',
        'url_fetch_error': 'Ошибка получения URL!',
        'file_not_found': 'Файл не найден!',
        'download_failed': 'Скачивание не удалось!',
        'download_error': 'Ошибка скачивания!',
        'youtube_download_caption': '📺 **YouTube:** {title}',
        'tiktok_download_caption': '🎵 **TikTok:** {title}',
        'tiktok_audio_caption': '🎵 **TikTok Аудио:** {title}',
        'instagram_download_caption': '📸 **Instagram:** {title}',
        'instagram_audio_caption': '🎵 **Instagram Аудио:** {title}',
        'mp3_not_found': 'MP3 файл не найден!',
        'conversion_failed': 'Конвертация не удалась!',
        'invalid_url': '❌ Неверная ссылка!'
    },
    'en': {
        'select_language': '🌐 **Select language:**',
        'language_selected': '✅ Language selected!',
        'welcome_message': '🎵 **Hello {name}!**\n\n**Welcome to Ultra-Fast Music Bot!**\n\n🚀 **Features:**\n• 🔍 Fast music search\n• 🎙️ Audio recognition\n• 📱 Media download\n\n⚡ **All operations are fast!**',
        'search_music': '🔍 Search Music',
        'recognize_song': '🎙️ Recognize Song',
        'download_media': '📱 Download Media',
        'help': '❓ Help',
        'banned_message': '🚫 **You are banned!**\n\n📝 **Reason:** {reason}\n📅 **Date:** {date}',
        'mandatory_subscription': '📢 **Mandatory Subscription**\n\nTo use the bot, subscribe to the channels:',
        'check_subscription': '📢 Subscribe to channel',
        'verify_subscription': '✅ Verify subscription',
        'recognizing_audio': '🎙️ **Recognizing audio...**\n\n⏳ Please wait...',
        'recognition_success': 'Music recognized!',
        'recognition_failed': 'Music not recognized',
        'processing_youtube': '📺 **Downloading from YouTube**\n\n⏳ Preparing...',
        'processing_tiktok': '🎵 **Downloading from TikTok**\n\n⏳ Preparing...',
        'processing_instagram': '📸 **Downloading from Instagram**\n\n⏳ Preparing...',
        'retrying': '🔄 Retrying ({attempt}/3)...',
        'youtube_error': '❌ YouTube download error!',
        'tiktok_error': '❌ TikTok download error!',
        'instagram_error': '❌ Instagram download error: {error}',
        'no_formats': '❌ No download formats found!',
        'youtube_formats': '📺 **YouTube: {title}**\n\n📋 **Formats:**\n',
        'tiktok_formats': '🎵 **TikTok Video**\n\n🎤 **Author:** {author}\n📝 **Description:** {description}\n\n📋 **Formats:**',
        'instagram_formats': '📸 **Instagram Media**\n\n👤 **User:** {user}\n📝 **Description:** {caption}\n\n📋 **Formats:**',
        'video_mp4': '📹 Video (MP4)',
        'audio_mp3': '🎵 Audio (MP3)',
        'unknown': 'Unknown',
        'no_description': 'No description',
        'no_caption': 'No caption',
        'unknown_error': 'Unknown error',
        'no_media_found': 'No media found',
        'invalid_button': 'Invalid button!',
        'session_expired': 'Session expired!',
        'downloading_format': 'Downloading {format}...',
        'invalid_format': 'Invalid format!',
        'url_fetch_error': 'URL fetch error!',
        'file_not_found': 'File not found!',
        'download_failed': 'Download failed!',
        'download_error': 'Download error!',
        'youtube_download_caption': '📺 **YouTube:** {title}',
        'tiktok_download_caption': '🎵 **TikTok:** {title}',
        'tiktok_audio_caption': '🎵 **TikTok Audio:** {title}',
        'instagram_download_caption': '📸 **Instagram:** {title}',
        'instagram_audio_caption': '🎵 **Instagram Audio:** {title}',
        'mp3_not_found': 'MP3 file not found!',
        'conversion_failed': 'Conversion failed!',
        'invalid_url': '❌ Invalid URL!'
    }
}

def get_text(key: str, lang: str = 'uz') -> str:
    """Get text by key and language"""
    try:
        return TEXTS.get(lang, TEXTS['uz']).get(key, key)
    except:
        return key

def detect_language(text: str) -> str:
    """Detect language from text"""
    if not text:
        return 'uz'
    
    # Simple language detection
    cyrillic_chars = len(re.findall(r'[а-яё]', text.lower()))
    latin_chars = len(re.findall(r'[a-z]', text.lower()))
    
    if cyrillic_chars > latin_chars:
        return 'ru'
    elif latin_chars > 0:
        return 'en'
    else:
        return 'uz'

def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2"""
    if not text:
        return ""
    
    # Characters that need to be escaped in MarkdownV2
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    
    # Escape each character
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return text
