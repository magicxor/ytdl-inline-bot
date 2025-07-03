"""YouTube downloader inline bot package."""

from .main import main
from .bot_instance import bot, dp, router
from .config import *
from .models import VideoMetadata, InlineQueryResultType
from .utils import extract_youtube_video_id, get_best_video_audio_format, retry_operation, setup_cookies_file, create_ydl_opts_with_auth
from .handlers import start, inlinequery, chosen_inline_result, download_video_and_replace

__all__ = [
    "main",
    "bot",
    "dp",
    "router",
    "VideoMetadata",
    "InlineQueryResultType",
    "extract_youtube_video_id",
    "get_best_video_audio_format",
    "retry_operation",
    "setup_cookies_file",
    "create_ydl_opts_with_auth",
    "start",
    "inlinequery",
    "chosen_inline_result",
    "download_video_and_replace",
]