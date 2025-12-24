#!/usr/bin/env python
"""Bot handlers for the video downloader inline bot."""

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from aiogram import types
from aiogram.filters import Command
from aiogram.types import (
    InlineQueryResultVideo,
    InputMediaVideo,
    InputMediaPhoto,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    FSInputFile,
)

from .models import InlineQueryResultType
from .config import (
    VIP_USER_ID,
    RATE_LIMIT_WINDOW_MINUTES,
    MAX_VIDEO_SIZE,
    MAX_AUDIO_SIZE,
    MAX_TG_FILE_SIZE,
    MEDIA_CHAT_ID,
    PH_LOADING_VIDEO_URL,
    PH_THUMBNAIL_URL,
    PH_VIDEO_WIDTH,
    PH_VIDEO_HEIGHT,
    PH_VIDEO_DURATION,
    ERR_LOADING_VIDEO_URL,
    ERR_VIDEO_WIDTH,
    ERR_VIDEO_HEIGHT,
    ERR_VIDEO_DURATION,
    user_download_timestamps,
)
from .utils import (
    get_best_video_audio_format,
    retry_operation,
    async_download_video,
    extract_youtube_video_id,
    is_valid_url,
    is_youtube_url,
)
from .bot_instance import bot

logger: logging.Logger = logging.getLogger(__name__)


async def start(message: types.Message) -> None:
    """Send a message when the command /start is issued."""
    user = message.from_user
    if user is not None:
        await message.reply(f"Hi {user.mention_html()}! Paste a video link using an inline query!", parse_mode="HTML")


async def inlinequery(inline_query: types.InlineQuery) -> None:
    """Handles inline queries."""
    user_id: int = inline_query.from_user.id
    current_time: datetime = datetime.now()

    # Rate limiting for non-VIP users
    if user_id != VIP_USER_ID:
        last_download_time: datetime | None = user_download_timestamps.get(user_id)
        if last_download_time and (current_time - last_download_time < timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)):
            logger.info(f"User {user_id} exceeded the rate limit.")
            return  # Early return to save resources and API quota

    query: str = inline_query.query
    if not query:
        return

    if is_valid_url(query):
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


async def chosen_inline_result(chosen_result: types.ChosenInlineResult) -> None:
    """Handles when a user selects an inline result."""
    user_id: int = chosen_result.from_user.id
    logger.info(f"Chosen inline result: {chosen_result.result_id}")
    inline_message_id: str | None = chosen_result.inline_message_id
    query: str = chosen_result.query
    if inline_message_id is not None:
        await download_video_and_replace(query, inline_message_id, user_id)


async def download_video_and_replace(url: str, inline_message_id: str, user_id: int) -> None:
    """Downloads a video asynchronously and replaces the placeholder."""
    try:
        logger.info(f"Downloading video: {url}; inline_message_id={inline_message_id}")

        # Rate limiting for non-VIP users
        if user_id != VIP_USER_ID:
            current_time: datetime = datetime.now()
            last_download_time: datetime | None = user_download_timestamps.get(user_id)

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
        video_size: int = metadata.best_video.get('filesize') or 0
        audio_size: int = metadata.best_audio.get('filesize') or 0
        total_size: int = video_size + audio_size
        if total_size > MAX_TG_FILE_SIZE:
            raise Exception(f"Combined video and audio filesize ({total_size} bytes) exceeds {MAX_TG_FILE_SIZE // (1024 * 1024)} MB limit.")

        # Generate a unique filename for the output
        output_file: str = f"download_{uuid.uuid4().hex}.mp4"

        # yt-dlp options for downloading and merging video and audio
        ydl_opts: Dict[str, Any] = {
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
                file_size: int = os.path.getsize(output_file)

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
        logger.exception(f"Error replacing the placeholder video: {e}")
        await _handle_download_error(url, inline_message_id)


async def _handle_download_error(url: str, inline_message_id: str) -> None:
    """Handle download error with YouTube-specific thumbnail fallback or generic error."""
    video_name: str = "Failed to download video."
    
    # Try to fetch page title for better error message
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            r = await client.get(url)
            soup = BeautifulSoup(r.text, "html.parser")
            title_tag = soup.find("title")
            if isinstance(title_tag, Tag) and title_tag.string:
                video_name = title_tag.string.strip()
    except Exception as fetch_err:
        logger.exception(f"Error fetching video page or parsing title: {fetch_err}")

    # YouTube-specific: try to show thumbnail image
    if is_youtube_url(url):
        try:
            video_id: str | None = extract_youtube_video_id(url)
            if video_id:
                thumbnail_url: str = f"https://img.youtube.com/vi/{video_id}/0.jpg"
                await bot.edit_message_media(
                    inline_message_id=inline_message_id,
                    media=InputMediaPhoto(
                        media=thumbnail_url,
                        caption=f"{video_name}\n{url}"
                    )
                )
                return
        except Exception as yt_err:
            logger.exception(f"Error replacing with YouTube thumbnail: {yt_err}")

    # Generic fallback for non-YouTube or if YouTube thumbnail failed
    try:
        await bot.edit_message_media(
            inline_message_id=inline_message_id,
            media=InputMediaVideo(
                media=ERR_LOADING_VIDEO_URL,
                caption=f"{video_name}\n{url}",
                width=ERR_VIDEO_WIDTH,
                height=ERR_VIDEO_HEIGHT,
                duration=ERR_VIDEO_DURATION,
                supports_streaming=False
            )
        )
    except Exception as fallback_err:
        logger.exception(f"Error showing fallback error video: {fallback_err}")
