#!/usr/bin/env python
import logging
import os
import uuid
import asyncio
from datetime import datetime, timedelta
from telegram import InlineQueryResultVideo, Update, InputMediaVideo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, InlineQueryHandler, ChosenInlineResultHandler
from yt_dlp import YoutubeDL

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)  # DO NOT MODIFY THIS LINE

logger = logging.getLogger(__name__)

# Constants loaded from environment variables with fallback values
MAX_VIDEO_SIZE = int(os.environ.get("MAX_VIDEO_SIZE", 15728640))  # 15 MB in bytes
MAX_AUDIO_SIZE = int(os.environ.get("MAX_AUDIO_SIZE", 8388608))   # 8 MB in bytes
VIP_USER_ID = int(os.environ.get("VIP_USER_ID", 282614687))  # User ID for VIP access
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "my_token")
ERR_LOADING_VIDEO_URL = os.environ.get("ERR_LOADING_VIDEO_URL", "https://magicxor.github.io/static/ytdl-inline-bot/error_v1.mp4")
ERR_THUMBNAIL_URL = os.environ.get("ERR_THUMBNAIL_URL", "https://magicxor.github.io/static/ytdl-inline-bot/error_v1.jpg")
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

# Dictionary to track user download attempts for rate limiting
user_download_timestamps = {}

class VideoMetadata:
    def __init__(self, best_video, best_audio, title, duration, width, height):
        self.best_video = best_video
        self.best_audio = best_audio
        self.title = title
        self.duration = duration
        self.width = width
        self.height = height

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! Type a YouTube link using an inline query!"
    )

def get_best_video_audio_format(url: str):
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
        duration = info.get('duration', 0)
        duration_string = info.get('duration_string', 'N/A')
        width = info.get('width', 'N/A')
        height = info.get('height', 'N/A')

        logger.info(f"Video title: {title}; duration: {duration} seconds; width: {width}; height: {height}; duration_string: {duration_string}")

        # Filter video formats based on criteria
        video_formats = [
            f for f in formats
            if f.get('vcodec') != 'none' and f.get('protocol') == 'https' and f.get('filesize') is not None
        ]
        video_formats.sort(key=lambda x: x['filesize'], reverse=True)
        best_video = next((f for f in video_formats if f['filesize'] <= MAX_VIDEO_SIZE), None)
        if not best_video and video_formats:
            # Choose the smallest video if none fit within the 15 MB constraint
            best_video = min(video_formats, key=lambda x: x['filesize'])

        # Filter audio formats based on criteria
        audio_formats = [
            f for f in formats
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('protocol') == 'https' and f.get('filesize') is not None
        ]
        audio_formats.sort(key=lambda x: x['filesize'], reverse=True)
        best_audio = next((f for f in audio_formats if f['filesize'] <= MAX_AUDIO_SIZE), None)
        if not best_audio and audio_formats:
            # Choose the smallest audio if none fit within the 8 MB constraint
            best_audio = min(audio_formats, key=lambda x: x['filesize'])

        logger.info(f"Best video format: {best_video}; best audio format: {best_audio}")

    return VideoMetadata(best_video, best_audio, title, duration, width, height)

async def retry_operation(coro, max_retries=2, delay=1, *args, **kwargs):
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

async def download_video_and_replace(url: str, inline_message_id: str, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Downloads a video asynchronously and replaces the placeholder."""
    try:
        logger.info(f"Downloading video: {url}; inline_message_id={inline_message_id}")

        # Rate limiting for non-VIP users
        if user_id != VIP_USER_ID:
            current_time = datetime.now()
            last_download_time = user_download_timestamps.get(user_id)

            if last_download_time and (current_time - last_download_time < timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)):
                await context.bot.edit_message_caption(
                    inline_message_id=inline_message_id,
                    caption=f"Rate limit exceeded. Please wait {RATE_LIMIT_WINDOW_MINUTES} minute(s) before requesting another download."
                )
                return

        metadata = get_best_video_audio_format(url)
        if not metadata.best_video:
            await context.bot.edit_message_caption(
                inline_message_id=inline_message_id,
                caption="No suitable video format found under 15 MB."
            )
            return
        if not metadata.best_audio:
            await context.bot.edit_message_caption(
                inline_message_id=inline_message_id,
                caption="No suitable audio format found under 8 MB."
            )
            return

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
        await retry_operation(async_download_video, max_retries=2, delay=1, ydl_opts=ydl_opts, url=url)

        # Once the video is downloaded, replace the placeholder
        if os.path.exists(output_file):
            with open(output_file, 'rb') as video_file:
                logger.info(f"Replacing video: {url}; inline_message_id={inline_message_id}")
                msg = await retry_operation(context.bot.send_video, max_retries=2, delay=1, chat_id=MEDIA_CHAT_ID, video=video_file, caption=(metadata.title + " " + url), width=metadata.width, height=metadata.height, duration=metadata.duration, supports_streaming=True)
                await context.bot.edit_message_media(
                    inline_message_id=inline_message_id,
                    media=InputMediaVideo(media=msg.video.file_id, caption=(metadata.title + " " + url), width=metadata.width, height=metadata.height, duration=metadata.duration, supports_streaming=True)
                )

            # Update rate limit timestamp for non-VIP users only on successful download
            if user_id != VIP_USER_ID:
                user_download_timestamps[user_id] = datetime.now()

            # Optionally, clean up the downloaded file
            os.remove(output_file)
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        await context.bot.edit_message_media(
            inline_message_id=inline_message_id,
            media=InputMediaVideo(media=ERR_LOADING_VIDEO_URL, caption="Failed to download the video.", width=ERR_VIDEO_WIDTH, height=ERR_VIDEO_HEIGHT, duration=ERR_VIDEO_DURATION, supports_streaming=False)
        )

async def async_download_video(ydl_opts, url):
    """Asynchronously downloads a video using yt-dlp."""
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

async def inlinequery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles inline queries."""
    user_id = update.effective_user.id
    current_time = datetime.now()

    # Rate limiting for non-VIP users
    if user_id != VIP_USER_ID:
        last_download_time = user_download_timestamps.get(user_id)
        if last_download_time and (current_time - last_download_time < timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)):
            logger.info(f"User {user_id} exceeded the rate limit.")
            return  # Early return to save resources and API quota

    query: str = update.inline_query.query
    if not query:
        return

    if query.startswith("https://youtu.be/") or query.startswith("https://www.youtube.com/watch") or query.startswith("https://youtube.com/watch") or query.startswith("https://m.youtube.com/watch") or query.startswith("https://youtube.com/shorts/") or query.startswith("https://www.youtube.com/shorts/"):
        # Send a placeholder with loading video
        results = [
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
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Please wait...", callback_data=str(uuid.uuid4()))]
                ])
            )
        ]
        await update.inline_query.answer(results)

async def chosen_inline_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles when a user selects an inline result."""
    user_id = update.effective_user.id
    logger.info(f"Chosen inline result: {update.chosen_inline_result.result_id}")
    inline_message_id = update.chosen_inline_result.inline_message_id
    query = update.chosen_inline_result.query
    await download_video_and_replace(query, inline_message_id, context, user_id)

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(InlineQueryHandler(inlinequery))
    application.add_handler(ChosenInlineResultHandler(chosen_inline_result))

    try:
        # Run the bot until the user presses Ctrl-C
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\nBot has been stopped by the user.")

if __name__ == "__main__":
    main()
