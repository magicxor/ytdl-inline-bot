#!/usr/bin/env python
"""Utility functions for the video downloader inline bot."""

import logging
import re
import asyncio
import base64
import os
import tempfile
from typing import Optional, Dict, Any, TypeVar, Callable, Awaitable
from urllib.parse import urlparse, parse_qs, ParseResult

from yt_dlp import YoutubeDL

from .models import VideoMetadata
from .config import MAX_VIDEO_SIZE, MAX_AUDIO_SIZE, PREFERRED_AUDIO_LANGUAGES, BOT_COOKIES_BASE64, BOT_USER_AGENT

logger: logging.Logger = logging.getLogger(__name__)

T = TypeVar('T')

# Global variable to store cookies file path
_cookies_file_path: Optional[str] = None


def setup_cookies_file() -> Optional[str]:
    """Decode base64 cookies and save to a temporary file. Returns the file path or None if no cookies."""
    global _cookies_file_path
    
    if _cookies_file_path and os.path.exists(_cookies_file_path):
        return _cookies_file_path
    
    if not BOT_COOKIES_BASE64:
        return None
    
    try:
        # Decode base64 cookies
        decoded_cookies: bytes = base64.b64decode(BOT_COOKIES_BASE64)
        cookies_content: str = decoded_cookies.decode('utf-8')
        
        # Create a temporary file for cookies
        temp_dir: str = tempfile.gettempdir()
        _cookies_file_path = os.path.join(temp_dir, 'ytdl_bot_cookies.txt')
        
        with open(_cookies_file_path, 'w', encoding='utf-8') as f:
            f.write(cookies_content)
        
        logger.info(f"Cookies file created at: {_cookies_file_path}")
        return _cookies_file_path
    except Exception as e:
        logger.exception(f"Failed to setup cookies file: {e}")
        return None


def create_ydl_opts_with_auth(base_opts: Dict[str, Any]) -> Dict[str, Any]:
    """Create yt-dlp options with authentication (cookies and user agent)."""
    ydl_opts: Dict[str, Any] = base_opts.copy()
    
    # Add cookies if available
    cookies_file: Optional[str] = setup_cookies_file()
    if cookies_file:
        ydl_opts['cookiefile'] = cookies_file
    
    # Add user agent if available
    if BOT_USER_AGENT:
        ydl_opts['http_headers'] = ydl_opts.get('http_headers', {})
        ydl_opts['http_headers']['User-Agent'] = BOT_USER_AGENT
    
    return ydl_opts


YOUTUBE_BASE_DOMAINS: tuple[str, ...] = (
    'youtube.com',
    'youtu.be',
)


def is_valid_url(url: str) -> bool:
    """Check if the given string is a valid http/https URL."""
    try:
        parsed: ParseResult = urlparse(url)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except Exception:
        return False


def is_youtube_url(url: str) -> bool:
    """Check if the given URL is a YouTube URL (including subdomains)."""
    try:
        parsed: ParseResult = urlparse(url)
        hostname: str | None = parsed.hostname
        if hostname is None:
            return False
        # Match exact domain or any subdomain (e.g., www.youtube.com, m.youtube.com)
        # but NOT domains like youtube.com.evil.com
        for base_domain in YOUTUBE_BASE_DOMAINS:
            if hostname == base_domain or hostname.endswith('.' + base_domain):
                return True
        return False
    except Exception:
        return False


def extract_youtube_video_id(url: str) -> Optional[str]:
    """Extract the YouTube video ID from various YouTube URL formats."""
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
    """Get the best video and audio formats that meet the specified constraints."""
    base_ydl_opts: Dict[str, Any] = {
        'quiet': True,
    }
    
    info: Optional[Dict[str, Any]] = None
    is_youtube: bool = is_youtube_url(url)
    
    # Try with authentication first for YouTube URLs only
    if is_youtube and (BOT_COOKIES_BASE64 or BOT_USER_AGENT):
        try:
            ydl_opts_with_auth: Dict[str, Any] = create_ydl_opts_with_auth(base_ydl_opts)
            logger.info("Attempting to extract YouTube video info with authentication...")
            with YoutubeDL(ydl_opts_with_auth) as ydl:
                info = ydl.extract_info(url, download=False)
            logger.info("Successfully extracted YouTube video info with authentication")
        except Exception as e:
            logger.warning(f"Failed to extract YouTube video info with authentication: {e}. Falling back to default behavior.", exc_info=True)
            info = None
    
    # Fallback to default behavior if auth failed or not available (or non-YouTube URL)
    if info is None:
        logger.info(f"Attempting to extract video info with default settings (YouTube: {is_youtube})...")
        with YoutubeDL(base_ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    
    # Build title: use YouTube video ID for YouTube, or generic fallback for other sites
    video_id: Optional[str] = extract_youtube_video_id(url) if is_youtube else None
    default_title: str = f'Video_{video_id}' if video_id else 'Unknown_Video'
    title: str = info.get('fulltitle') or info.get('title') or default_title
    duration: int = int(info.get('duration', 0) or 0)
    
    formats: list[Dict[str, Any]] = info.get('formats', [])
    
    # For YouTube: require filesize info for size limit checks
    # For other sites: allow unknown filesize (many sites don't provide it)
    best_video: Optional[Dict[str, Any]] = _select_best_video_format(formats, is_youtube)
    best_audio: Optional[Dict[str, Any]] = _select_best_audio_format(formats, is_youtube)
    
    width: Optional[int] = None
    height: Optional[int] = None
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


def _select_best_video_format(
    formats: list[Dict[str, Any]],
    require_filesize: bool
) -> Optional[Dict[str, Any]]:
    """Select the best video format based on constraints."""
    # Filter video formats: must have video codec
    all_video_formats: list[Dict[str, Any]] = [
        f for f in formats if f.get('vcodec') != 'none'
    ]
    
    if not all_video_formats:
        return None
    
    # Separate formats with known filesize
    formats_with_size: list[Dict[str, Any]] = [
        f for f in all_video_formats if f.get('filesize')
    ]
    
    # For YouTube (require_filesize=True): only use formats with known filesize
    # For other sites: prefer formats with size, but allow unknown if none available
    if require_filesize:
        video_formats: list[Dict[str, Any]] = formats_with_size
    else:
        video_formats = formats_with_size if formats_with_size else all_video_formats
    
    if not video_formats:
        return None
    
    # Prefer H.264 (avc1) codec for better compatibility
    avc1_formats: list[Dict[str, Any]] = [
        f for f in video_formats if 'avc1' in (f.get('vcodec') or '')
    ]
    
    best_video: Optional[Dict[str, Any]] = None
    
    # Try avc1 formats first
    if avc1_formats:
        best_video = _find_best_format_by_size(avc1_formats, MAX_VIDEO_SIZE, require_filesize)
    
    # Fallback to any video format
    if not best_video:
        best_video = _find_best_format_by_size(video_formats, MAX_VIDEO_SIZE, require_filesize)
    
    return best_video


def _select_best_audio_format(
    formats: list[Dict[str, Any]],
    require_filesize: bool
) -> Optional[Dict[str, Any]]:
    """Select the best audio format based on constraints."""
    # Filter audio-only formats: must have audio codec, no video
    all_audio_formats: list[Dict[str, Any]] = [
        f for f in formats
        if f.get('acodec') != 'none' and f.get('vcodec') in ('none', None)
    ]
    
    # If no audio-only formats, try formats that have audio (including video+audio)
    if not all_audio_formats:
        all_audio_formats = [f for f in formats if f.get('acodec') != 'none']
    
    if not all_audio_formats:
        return None
    
    # Separate formats with known filesize
    formats_with_size: list[Dict[str, Any]] = [
        f for f in all_audio_formats if f.get('filesize')
    ]
    
    if require_filesize:
        audio_formats: list[Dict[str, Any]] = formats_with_size
    else:
        audio_formats = formats_with_size if formats_with_size else all_audio_formats
    
    if not audio_formats:
        return None
    
    best_audio: Optional[Dict[str, Any]] = None
    
    # Prioritize by preferred languages (YouTube-specific, but won't hurt for others)
    for lang in PREFERRED_AUDIO_LANGUAGES:
        lang_formats: list[Dict[str, Any]] = [
            f for f in audio_formats
            if f.get('language') == lang or lang.startswith(f.get('language') or '')
        ]
        if lang_formats:
            best_audio = _find_best_audio_by_bitrate(lang_formats, MAX_AUDIO_SIZE, require_filesize)
            if best_audio:
                break
    
    # Fallback to best quality audio without language preference
    if not best_audio:
        best_audio = _find_best_audio_by_bitrate(audio_formats, MAX_AUDIO_SIZE, require_filesize)
    
    return best_audio


def _find_best_format_by_size(
    formats: list[Dict[str, Any]],
    max_size: int,
    require_filesize: bool
) -> Optional[Dict[str, Any]]:
    """Find the best video format by height, respecting size constraints if known."""
    # Sort by height descending (best quality first)
    sorted_formats: list[Dict[str, Any]] = sorted(
        formats, key=lambda x: x.get('height') or 0, reverse=True
    )
    
    # First pass: find format that fits within size limit
    for f in sorted_formats:
        filesize: int = f.get('filesize') or 0
        if filesize > 0:
            if filesize <= max_size:
                return f
        elif not require_filesize:
            # Unknown filesize allowed for non-YouTube
            return f
    
    # Second pass: if require_filesize, get smallest available
    if require_filesize and formats:
        return min(formats, key=lambda x: x.get('filesize') or float('inf'))
    
    return None


def _find_best_audio_by_bitrate(
    formats: list[Dict[str, Any]],
    max_size: int,
    require_filesize: bool
) -> Optional[Dict[str, Any]]:
    """Find the best audio format by bitrate, respecting size constraints if known."""
    # Sort by audio bitrate descending (best quality first)
    sorted_formats: list[Dict[str, Any]] = sorted(
        formats, key=lambda x: x.get('abr') or 0, reverse=True
    )
    
    # First pass: find format that fits within size limit
    for f in sorted_formats:
        filesize: int = f.get('filesize') or 0
        if filesize > 0:
            if filesize <= max_size:
                return f
        elif not require_filesize:
            return f
    
    # Second pass: if require_filesize, get smallest available
    if require_filesize and formats:
        return min(formats, key=lambda x: x.get('filesize') or float('inf'))
    
    return None


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
    """Asynchronously downloads a video using yt-dlp with authentication fallback."""
    loop = asyncio.get_event_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, sync_download_video_with_fallback, ydl_opts, url),
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


def sync_download_video_with_fallback(ydl_opts: Dict[str, Any], url: str) -> None:
    """Synchronously download a video using yt-dlp with YouTube auth fallback."""
    is_youtube: bool = is_youtube_url(url)
    
    # Try with authentication first for YouTube URLs only
    if is_youtube and (BOT_COOKIES_BASE64 or BOT_USER_AGENT):
        try:
            ydl_opts_with_auth: Dict[str, Any] = create_ydl_opts_with_auth(ydl_opts)
            logger.info("Attempting to download YouTube video with authentication...")
            with YoutubeDL(ydl_opts_with_auth) as ydl:
                ydl.download([url])
            logger.info("Successfully downloaded YouTube video with authentication")
            return
        except Exception as e:
            logger.warning(f"Failed to download YouTube video with authentication: {e}. Falling back to default behavior.", exc_info=True)
    
    # Fallback to default behavior (or direct download for non-YouTube)
    logger.info(f"Attempting to download video with default settings (YouTube: {is_youtube})...")
    sync_download_video(ydl_opts, url)
