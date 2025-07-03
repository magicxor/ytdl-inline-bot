#!/usr/bin/env python
"""Utility functions for the YouTube downloader inline bot."""

import logging
import re
import asyncio
from typing import Optional, Dict, Any, TypeVar, Callable, Awaitable
from urllib.parse import urlparse, parse_qs

from yt_dlp import YoutubeDL

from .models import VideoMetadata
from .config import MAX_VIDEO_SIZE, MAX_AUDIO_SIZE, PREFERRED_AUDIO_LANGUAGES

logger: logging.Logger = logging.getLogger(__name__)

T = TypeVar('T')


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


def get_best_video_audio_format(url: str) -> VideoMetadata:
    """Gets the best video and audio formats that meet the specified constraints and returns a VideoMetadata object."""
    ydl_opts = {
        'quiet': True,
    }
    
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        video_id = extract_youtube_video_id(url)
        title = info.get('fulltitle', f'Video_{video_id}' if video_id else 'Unknown_Video')
        duration = int(info.get('duration', 0) or 0)
        
        # Find the best video format based on our criteria
        best_video = None
        best_audio = None
        
        formats = info.get('formats', [])
        
        # Find the best video format (preferably with audio)
        video_formats = [f for f in formats if f.get('vcodec') != 'none' and f.get('filesize')]
        
        # Find the best video format that meets our size constraints
        for f in sorted(video_formats, key=lambda x: x.get('height', 0), reverse=True):
            if f.get('filesize', 0) <= MAX_VIDEO_SIZE:
                best_video = f
                break
        
        # If no video format meets our constraints, get the smallest one
        if not best_video and video_formats:
            best_video = min(video_formats, key=lambda x: x.get('filesize', float('inf')))
        
        # Find the best audio format
        audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('filesize')]
        
        # Prioritize audio formats by language preference
        for lang in PREFERRED_AUDIO_LANGUAGES:
            for f in sorted(audio_formats, key=lambda x: x.get('abr', 0), reverse=True):
                if f.get('filesize', 0) <= MAX_AUDIO_SIZE:
                    if f.get('language') == lang or lang.startswith(f.get('language', '')):
                        best_audio = f
                        break
            if best_audio:
                break
        
        # If no language preference match, get the best quality audio that meets size constraints
        if not best_audio:
            for f in sorted(audio_formats, key=lambda x: x.get('abr', 0), reverse=True):
                if f.get('filesize', 0) <= MAX_AUDIO_SIZE:
                    best_audio = f
                    break
        
        # If no audio format meets our constraints, get the smallest one
        if not best_audio and audio_formats:
            best_audio = min(audio_formats, key=lambda x: x.get('filesize', float('inf')))
        
        width = None
        height = None
        if best_video:
            width = best_video.get('width')
            height = best_video.get('height')
        
        return VideoMetadata(
            best_video=best_video,
            best_audio=best_audio,
            title=title,
            duration=duration,
            width=width,
            height=height
        )


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
            if attempt == max_retries:
                raise
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay} seconds...")
            await asyncio.sleep(delay)
    
    # This should never be reached, but added for type safety
    raise RuntimeError("Max retries exceeded")


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
    """Synchronously downloads a video using yt-dlp."""
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
