#!/usr/bin/env python
import logging
import os
from typing import TypeAlias, Union, Optional, Dict, Any, List, TypeVar, Callable, Awaitable
import uuid
import asyncio
import re
import httpx
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.types import (
    InlineQueryResultCachedAudio,
    InlineQueryResultCachedDocument,
    InlineQueryResultCachedGif,
    InlineQueryResultCachedMpeg4Gif,
    InlineQueryResultCachedPhoto,
    InlineQueryResultCachedSticker,
    InlineQueryResultCachedVideo,
    InlineQueryResultCachedVoice,
    InlineQueryResultArticle,
    InlineQueryResultAudio,
    InlineQueryResultContact,
    InlineQueryResultGame,
    InlineQueryResultDocument,
    InlineQueryResultGif,
    InlineQueryResultLocation,
    InlineQueryResultMpeg4Gif,
    InlineQueryResultPhoto,
    InlineQueryResultVenue,
    InlineQueryResultVideo,
    InlineQueryResultVoice,
    InputMediaVideo,
    InputMediaPhoto,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    FSInputFile,
)
from yt_dlp import YoutubeDL
from bs4 import BeautifulSoup
from bs4.element import Tag

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
)
logging.getLogger("httpx").setLevel(logging.WARNING)  # DO NOT MODIFY THIS LINE

logger = logging.getLogger(__name__)

# Constants loaded from environment variables with fallback values
MAX_VIDEO_SIZE = int(os.environ.get("MAX_VIDEO_SIZE", 15728640))  # 15 MB in bytes
MAX_AUDIO_SIZE = int(os.environ.get("MAX_AUDIO_SIZE", 8388608))   # 8 MB in bytes
MAX_TG_FILE_SIZE = int(os.environ.get("MAX_TG_FILE_SIZE", 52428800))  # 50 MB in bytes
VIP_USER_ID = int(os.environ.get("VIP_USER_ID", 282614687))  # User ID for VIP access
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "my_token")
ERR_LOADING_VIDEO_URL = os.environ.get("ERR_LOADING_VIDEO_URL", "https://magicxor.github.io/static/ytdl-inline-bot/error_v1.mp4")
ERR_VIDEO_WIDTH = int(os.environ.get("ERR_VIDEO_WIDTH", 640))
ERR_VIDEO_HEIGHT = int(os.environ.get("ERR_VIDEO_HEIGHT", 480))
ERR_VIDEO_DURATION = int(os.environ.get("ERR_VIDEO_DURATION", 5))  # seconds
PH_LOADING_VIDEO_URL = os.environ.get("PH_LOADING_VIDEO_URL", "https://magicxor.github.io/static/ytdl-inline-bot/loading_v2.mp4")
PH_THUMBNAIL_URL = os.environ.get("PH_THUMBNAIL_URL", "https://magicxor.github.io/static/ytdl-inline-bot/loading_v1.jpg")
PH_VIDEO_WIDTH = int(os.environ.get("PH_VIDEO_WIDTH", 1024))
PH_VIDEO_HEIGHT = int(os.environ.get("PH_VIDEO_HEIGHT", 576))
PH_VIDEO_DURATION = int(os.environ.get("PH_VIDEO_DURATION", 10))  # seconds
MEDIA_CHAT_ID = int(os.environ.get("MEDIA_CHAT_ID", -1002389753204))  # chat ID that the bot can send media to
RATE_LIMIT_WINDOW_MINUTES = int(os.environ.get("RATE_LIMIT_WINDOW_MINUTES", 1))  # Rate limit window in minutes
PREFERRED_AUDIO_LANGUAGES = [lang.strip() for lang in os.environ.get("PREFERRED_AUDIO_LANGUAGES", "en-US,en,ru-RU,ru").split(',') if lang.strip()]

# Dictionary to track user download attempts for rate limiting
user_download_timestamps: Dict[int, datetime] = {}

@dataclass
class VideoMetadata:
    best_video: Optional[Dict[str, Any]]
    best_audio: Optional[Dict[str, Any]]
    title: str
    duration: int  # Changed to int
    width: Optional[int]
    height: Optional[int]

InlineQueryResultType: TypeAlias = List[
    Union[
        InlineQueryResultCachedAudio,
        InlineQueryResultCachedDocument,
        InlineQueryResultCachedGif,
        InlineQueryResultCachedMpeg4Gif,
        InlineQueryResultCachedPhoto,
        InlineQueryResultCachedSticker,
        InlineQueryResultCachedVideo,
        InlineQueryResultCachedVoice,
        InlineQueryResultArticle,
        InlineQueryResultAudio,
        InlineQueryResultContact,
        InlineQueryResultGame,
        InlineQueryResultDocument,
        InlineQueryResultGif,
        InlineQueryResultLocation,
        InlineQueryResultMpeg4Gif,
        InlineQueryResultPhoto,
        InlineQueryResultVenue,
        InlineQueryResultVideo,
        InlineQueryResultVoice,
    ]
]

# Create bot and dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

def extract_youtube_video_id(url: str) -> Optional[str]:
    """
    Extracts the YouTube video ID from various YouTube URL formats.
    """
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    if 'v' in query_params:
        return query_params['v'][0]
    elif parsed_url.hostname in ['youtu.be']:
        return parsed_url.path[1:]
    elif '/embed/' in parsed_url.path:
        return parsed_url.path.split('/embed/')[1]
    elif '/shorts/' in parsed_url.path:
        return parsed_url.path.split('/shorts/')[1].split('/')[0]
    elif '/watch/' in parsed_url.path:
        return parsed_url.path.split('/watch/')[1]
    else:
        # For other cases, try to extract the 11-character video ID using regex
        match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
        if match:
            return match.group(1)
    return None

@router.message(Command("start"))
async def start(message: types.Message) -> None:
    """Send a message when the command /start is issued."""
    user = message.from_user
    if user is not None:
        await message.reply(f"Hi {user.mention_html()}! Type a YouTube link using an inline query!", parse_mode="HTML")

def get_best_video_audio_format(url: str) -> VideoMetadata:
    """Gets the best video and audio formats that meet the specified constraints and returns a VideoMetadata object."""
    ydl_opts = {
        'quiet': True,
        'format': 'best',
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])

        # Extract additional metadata
        title = info.get('title', 'Unknown Title')
        duration = int(info.get('duration', 0))
        duration_string = info.get('duration_string', 'N/A')
        width = info.get('width', None)
        height = info.get('height', None)

        logger.info(f"Video title: {title}; duration: {duration} seconds; width: {width}; height: {height}; duration_string: {duration_string}")

        # Filter video formats based on criteria
        video_formats = [
            f for f in formats
            if f.get('vcodec') != 'none' and f.get('protocol') == 'https' and f.get('filesize') is not None
        ]
        video_formats.sort(key=lambda x: x['filesize'], reverse=True)

        # First, try to select the largest file with 'avc1' in 'vcodec' that fits within MAX_VIDEO_SIZE
        best_video = next(
            (f for f in video_formats if f['filesize'] <= MAX_VIDEO_SIZE and 'avc1' in f.get('vcodec', '')), None
        )
        if not best_video and video_formats:
            # If not found, revert to the original behavior
            best_video = next((f for f in video_formats if f['filesize'] <= MAX_VIDEO_SIZE), None)
            if not best_video and video_formats:
                # Choose the smallest video if none fit within the constraint
                best_video = min(video_formats, key=lambda x: x['filesize'])

        # Filter audio formats based on criteria
        audio_formats = [
            f for f in formats
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('protocol') == 'https' and f.get('filesize') is not None
        ]

        # Custom sort key for audio formats
        def audio_sort_key(f):
            lang = f.get('language')
            try:
                lang_priority = PREFERRED_AUDIO_LANGUAGES.index(lang)
            except ValueError:
                lang_priority = len(PREFERRED_AUDIO_LANGUAGES)  # Lower priority for other languages
            filesize = f.get('filesize', 0)
            return (lang_priority, -filesize)  # Sort by lang priority (asc), then by filesize (desc)

        audio_formats.sort(key=audio_sort_key)
        best_audio = next((f for f in audio_formats if f['filesize'] <= MAX_AUDIO_SIZE), None)
        if not best_audio and audio_formats:
            # Choose the smallest audio if none fit within the constraint
            best_audio = min(audio_formats, key=lambda x: x['filesize'])

        logger.info(f"Best video format: {best_video}; \n\nBest audio format: {best_audio}")

    return VideoMetadata(best_video, best_audio, title, duration, width, height)

T = TypeVar('T')

async def retry_operation(
    coro: Callable[..., Awaitable[T]],
    max_retries: int = 2,
    delay: float = 1,
    *args: Any,
    **kwargs: Any
) -> T:
    """Retries an asynchronous operation on failure up to a maximum number of retries."""
    for attempt in range(max_retries + 1):
        try:
            return await coro(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"Operation failed (attempt {attempt + 1}/{max_retries}). Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"Operation failed after {max_retries + 1} attempts.")
                raise e

    # unreachable code to make mypy happy
    # if we get here, all retries have failed
    raise Exception("Unexpected error in retry_operation")

async def download_video_and_replace(url: str, inline_message_id: str, user_id: int) -> None:
    """Downloads a video asynchronously and replaces the placeholder."""
    try:
        logger.info(f"Downloading video: {url}; inline_message_id={inline_message_id}")

        # Rate limiting for non-VIP users
        if user_id != VIP_USER_ID:
            current_time = datetime.now()
            last_download_time = user_download_timestamps.get(user_id)

            if last_download_time and (current_time - last_download_time < timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)):
                await bot.edit_message_caption(
                    inline_message_id=inline_message_id,
                    caption=f"Rate limit exceeded. Please wait {RATE_LIMIT_WINDOW_MINUTES} minute(s) before requesting another download."
                )
                raise Exception("Rate limit exceeded.")

        metadata = get_best_video_audio_format(url)
        if not metadata.best_video:
            await bot.edit_message_caption(
                inline_message_id=inline_message_id,
                caption=f"No suitable video format found under {MAX_VIDEO_SIZE // (1024 * 1024)} MB."
            )
            raise Exception(f"No suitable video format found under {MAX_VIDEO_SIZE} bytes.")
        if not metadata.best_audio:
            await bot.edit_message_caption(
                inline_message_id=inline_message_id,
                caption=f"No suitable audio format found under {MAX_AUDIO_SIZE // (1024 * 1024)} MB."
            )
            raise Exception(f"No suitable audio format found under {MAX_AUDIO_SIZE} bytes.")

        # Check if total size exceeds MAX_TG_FILE_SIZE
        total_size = metadata.best_video['filesize'] + metadata.best_audio['filesize']
        if total_size > MAX_TG_FILE_SIZE:
            raise Exception(f"Combined video and audio filesize ({total_size} bytes) exceeds {MAX_TG_FILE_SIZE // (1024 * 1024)} MB limit.")

        # Generate a unique filename for the output
        output_file = f"download_{uuid.uuid4().hex}.mp4"

        # yt-dlp options for downloading and merging video and audio
        ydl_opts = {
            'quiet': True,
            'format': f"{metadata.best_video['format_id']}+{metadata.best_audio['format_id']}",
            'outtmpl': output_file,
            'merge_output_format': 'mp4',  # Ensure merging into mp4 format
        }

        # Downloading the video and audio and merging with retry logic
        await retry_operation(async_download_video, max_retries=2, delay=1, ydl_opts=ydl_opts, url=url, timeout=60.0)

        # Once the video is downloaded, replace the placeholder
        if os.path.exists(output_file):
            with open(output_file, 'rb') as video_file:
                file_size = os.path.getsize(output_file)

                logger.info(f"Uploading the video {url} to the chat {MEDIA_CHAT_ID}; inline_message_id={inline_message_id}; file size={file_size} bytes; file name={output_file}")
                msg = await retry_operation(
                    bot.send_video,
                    max_retries=2,
                    delay=1,
                    chat_id=MEDIA_CHAT_ID,
                    video=FSInputFile(path=output_file),
                    caption=(metadata.title + " " + url),
                    width=metadata.width,
                    height=metadata.height,
                    duration=metadata.duration,
                    supports_streaming=True
                )

                # Ensure that msg.video is not None
                if msg.video is None:
                    raise ValueError("Failed to retrieve video from the sent message.")

                logger.info(f"Video uploaded. Replacing the placeholder with the video {msg.video.file_id}")
                await retry_operation(
                    bot.edit_message_media,
                    max_retries=2,
                    delay=1,
                    inline_message_id=inline_message_id,
                    media=InputMediaVideo(
                        media=msg.video.file_id,
                        caption=(metadata.title + " " + url),
                        width=metadata.width,
                        height=metadata.height,
                        duration=metadata.duration,
                        supports_streaming=True
                    )
                )

            # Update rate limit timestamp for non-VIP users only on successful download
            if user_id != VIP_USER_ID:
                user_download_timestamps[user_id] = datetime.now()

            # Optionally, clean up the downloaded file
            os.remove(output_file)
    except Exception as e:
        logger.error(f"Error replacing the placeholder video: {e}")

        # Attempt to replace placeholder video with thumbnail image
        video_name = "Failed to download video."
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await client.get(url)
                soup = BeautifulSoup(r.text, "html.parser")
                title_tag = soup.find("title")
                if isinstance(title_tag, Tag) and title_tag.string:
                    video_name = title_tag.string.strip()
        except Exception as fetch_err:
            logger.error(f"Error fetching video page or parsing title: {fetch_err}")

        # Use extracted video name instead of the hardcoded message
        try:
            video_id = extract_youtube_video_id(url)
            if video_id:
                thumbnail_url = f"https://img.youtube.com/vi/{video_id}/0.jpg"
                await bot.edit_message_media(
                    inline_message_id=inline_message_id,
                    media=InputMediaPhoto(
                        media=thumbnail_url,
                        caption=f"{video_name}\n{url}"
                    )
                )
            else:
                raise ValueError("Could not extract video ID")
        except Exception as e2:
            logger.error(f"Error replacing with thumbnail image: {e2}")
            # Fall back to current behavior
            await bot.edit_message_media(
                inline_message_id=inline_message_id,
                media=InputMediaVideo(media=ERR_LOADING_VIDEO_URL, caption="Failed to replace the placeholder video.", width=ERR_VIDEO_WIDTH, height=ERR_VIDEO_HEIGHT, duration=ERR_VIDEO_DURATION, supports_streaming=False)
            )

async def async_download_video(ydl_opts: Dict[str, Any], url: str, timeout: float = 60.0) -> None:
    """Asynchronously downloads a video using yt-dlp."""
    loop = asyncio.get_event_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, sync_download_video, ydl_opts, url),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        # Re-raise the timeout error to be handled by the caller
        # Or handle it here, e.g., log a message or notify the user
        raise

def sync_download_video(ydl_opts: Dict[str, Any], url: str) -> None:
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

@router.inline_query()
async def inlinequery(inline_query: types.InlineQuery) -> None:
    """Handles inline queries."""
    user_id = inline_query.from_user.id
    current_time = datetime.now()

    # Rate limiting for non-VIP users
    if user_id != VIP_USER_ID:
        last_download_time = user_download_timestamps.get(user_id)
        if last_download_time and (current_time - last_download_time < timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)):
            logger.info(f"User {user_id} exceeded the rate limit.")
            return  # Early return to save resources and API quota

    query: str = inline_query.query
    if not query:
        return

    if query.startswith(("https://youtu.be/", "https://www.youtube.com/watch", "https://youtube.com/watch", "https://m.youtube.com/watch", "https://youtube.com/shorts/", "https://www.youtube.com/shorts/")):
        # Send a placeholder with loading video
        results: InlineQueryResultType = [
            InlineQueryResultVideo(
                id=str(uuid.uuid4()),
                video_url=PH_LOADING_VIDEO_URL,
                title="Downloading...",
                caption="Please wait while the video is being processed. URL: " + query,
                mime_type="video/mp4",
                thumbnail_url=PH_THUMBNAIL_URL,
                video_width=PH_VIDEO_WIDTH,
                video_height=PH_VIDEO_HEIGHT,
                video_duration=PH_VIDEO_DURATION,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Please wait...", callback_data=str(uuid.uuid4()))]
                    ]
                )
            )
        ]
        await inline_query.answer(results)

@router.chosen_inline_result()
async def chosen_inline_result(chosen_result: types.ChosenInlineResult) -> None:
    """Handles when a user selects an inline result."""
    user_id = chosen_result.from_user.id
    logger.info(f"Chosen inline result: {chosen_result.result_id}")
    inline_message_id = chosen_result.inline_message_id
    query = chosen_result.query
    if inline_message_id is not None:
        await download_video_and_replace(query, inline_message_id, user_id)

async def main() -> None:
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\nBot has been stopped by the user.")
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
