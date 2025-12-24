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
    duration = int(info.get('duration', 0) or 0)
    
    # Find the best video format based on our criteria
    best_video = None
    best_audio = None
    
    formats = info.get('formats', [])
    
    # Find the best video format (preferably with audio)
    video_formats = [f for f in formats if f.get('vcodec') != 'none' and f.get('filesize')]
    
    # First, try to find the best video format with H.264 (avc1) codec that meets our size constraints
    avc1_formats = [f for f in video_formats if 'avc1' in f.get('vcodec', '')]
    if avc1_formats:
        for f in sorted(avc1_formats, key=lambda x: x.get('height') or 0, reverse=True):
            avc1_filesize: int = f.get('filesize') or 0
            if avc1_filesize > 0 and avc1_filesize <= MAX_VIDEO_SIZE:
                best_video = f
                break
    
    # If no avc1 format meets our constraints, use the general algorithm
    if not best_video:
        for f in sorted(video_formats, key=lambda x: x.get('height') or 0, reverse=True):
            general_filesize: int = f.get('filesize') or 0
            if general_filesize > 0 and general_filesize <= MAX_VIDEO_SIZE:
                best_video = f
                break
    
    # If no video format meets our constraints, get the smallest one (prefer avc1 if available)
    if not best_video and video_formats:
        if avc1_formats:
            best_video = min(avc1_formats, key=lambda x: x.get('filesize') or float('inf'))
        else:
            best_video = min(video_formats, key=lambda x: x.get('filesize') or float('inf'))
    
    # Find the best audio format
    audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('filesize')]
    
    # Prioritize audio formats by language preference
    # First, collect all audio formats that match preferred languages
    preferred_audio_formats: list[Dict[str, Any]] = []
    for lang in PREFERRED_AUDIO_LANGUAGES:
        for f in sorted(audio_formats, key=lambda x: x.get('abr') or 0, reverse=True):
            audio_filesize_lang: int = f.get('filesize') or 0
            if audio_filesize_lang > 0 and audio_filesize_lang <= MAX_AUDIO_SIZE:
                if f.get('language') == lang or lang.startswith(f.get('language') or ''):
                    preferred_audio_formats.append(f)
    
    # If we found preferred language formats, prioritize original ones
    if preferred_audio_formats:
        # Look for original audio track among preferred languages
        original_audio = None
        for f in preferred_audio_formats:
            # Check if this format is marked as original
            # yt-dlp often includes 'original' in the format note or language description
            format_note: str = f.get('format_note', '').lower()
            language_note: str = f.get('language', '')
            
            if 'original' in format_note or (language_note and 'original' in str(f).lower()):
                original_audio = f
                break
        
        # Use original if found, otherwise use the first preferred format
        best_audio = original_audio if original_audio else preferred_audio_formats[0]
    
    # If no language preference match, get the best quality audio that meets size constraints
    if not best_audio:
        for f in sorted(audio_formats, key=lambda x: x.get('abr') or 0, reverse=True):
            audio_filesize: int = f.get('filesize') or 0
            if audio_filesize > 0 and audio_filesize <= MAX_AUDIO_SIZE:
                best_audio = f
                break
    
    # If no audio format meets our constraints, get the smallest one
    if not best_audio and audio_formats:
        best_audio = min(audio_formats, key=lambda x: x.get('filesize') or float('inf'))
    
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
