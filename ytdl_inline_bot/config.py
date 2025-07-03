#!/usr/bin/env python
"""Configuration module for the YouTube downloader inline bot."""

import os
from typing import Dict, List
from datetime import datetime

# Constants loaded from environment variables with fallback values
MAX_VIDEO_SIZE: int = int(os.environ.get("MAX_VIDEO_SIZE", 15728640))  # 15 MB in bytes
MAX_AUDIO_SIZE: int = int(os.environ.get("MAX_AUDIO_SIZE", 8388608))   # 8 MB in bytes
MAX_TG_FILE_SIZE: int = int(os.environ.get("MAX_TG_FILE_SIZE", 52428800))  # 50 MB in bytes
VIP_USER_ID: int = int(os.environ.get("VIP_USER_ID", 282614687))  # User ID for VIP access
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "my_token")
ERR_LOADING_VIDEO_URL: str = os.environ.get("ERR_LOADING_VIDEO_URL", "https://magicxor.github.io/static/ytdl-inline-bot/error_v1.mp4")
ERR_VIDEO_WIDTH: int = int(os.environ.get("ERR_VIDEO_WIDTH", 640))
ERR_VIDEO_HEIGHT: int = int(os.environ.get("ERR_VIDEO_HEIGHT", 480))
ERR_VIDEO_DURATION: int = int(os.environ.get("ERR_VIDEO_DURATION", 5))  # seconds
PH_LOADING_VIDEO_URL: str = os.environ.get("PH_LOADING_VIDEO_URL", "https://magicxor.github.io/static/ytdl-inline-bot/loading_v2.mp4")
PH_THUMBNAIL_URL: str = os.environ.get("PH_THUMBNAIL_URL", "https://magicxor.github.io/static/ytdl-inline-bot/loading_v1.jpg")
PH_VIDEO_WIDTH: int = int(os.environ.get("PH_VIDEO_WIDTH", 1024))
PH_VIDEO_HEIGHT: int = int(os.environ.get("PH_VIDEO_HEIGHT", 576))
PH_VIDEO_DURATION: int = int(os.environ.get("PH_VIDEO_DURATION", 10))  # seconds
MEDIA_CHAT_ID: int = int(os.environ.get("MEDIA_CHAT_ID", -1002389753204))  # chat ID that the bot can send media to
RATE_LIMIT_WINDOW_MINUTES: int = int(os.environ.get("RATE_LIMIT_WINDOW_MINUTES", 1))  # Rate limit window in minutes
PREFERRED_AUDIO_LANGUAGES: List[str] = [lang.strip() for lang in os.environ.get("PREFERRED_AUDIO_LANGUAGES", "en-US,en,ru-RU,ru").split(',') if lang.strip()]

# Dictionary to track user download attempts for rate limiting
user_download_timestamps: Dict[int, datetime] = {}
