---
trigger: model_decision
description: This is a quick project overview. Apply this when you need documentation.
---

## Overview

Relevant source files
- [README.md](https://github.com/magicxor/ytdl-inline-bot/blob/22164776/README.md)
- [pyproject.toml](https://github.com/magicxor/ytdl-inline-bot/blob/22164776/pyproject.toml)
- [ytdl\_inline\_bot/bot.py](https://github.com/magicxor/ytdl-inline-bot/blob/22164776/ytdl_inline_bot/bot.py)

## Purpose and Scope

This document provides a high-level overview of the `ytdl-inline-bot` repository, a Telegram bot that enables users to download YouTube videos through inline queries. The bot processes YouTube URLs, downloads videos using `yt-dlp`, and delivers them back to users through the Telegram Bot API with rate limiting and VIP user support.

For detailed implementation specifics of the bot logic, see [Bot Implementation](/magicxor/ytdl-inline-bot/2.1-bot-implementation). For project configuration and dependency management, see [Project Configuration](/magicxor/ytdl-inline-bot/2.2-project-configuration) and [Dependency Management](/magicxor/ytdl-inline-bot/2.3-dependency-management). For deployment and CI/CD processes, see [CI/CD and Deployment](/magicxor/ytdl-inline-bot/4-cicd-and-deployment).

## System Architecture

The ytdl-inline-bot is a Python application built on the `aiogram` framework that integrates with external services to provide YouTube video downloading functionality through Telegram's inline query system.

## Video Processing Workflow

The bot implements a sophisticated video processing pipeline that handles user requests, downloads content, and manages delivery through Telegram's infrastructure.

## Key Features and Components

### Rate Limiting and VIP System

The bot implements a time-based rate limiting system that restricts non-VIP users to one download per configurable window:

| Component | Implementation | Configuration |
| --- | --- | --- |
| Rate Tracking | `user_download_timestamps: Dict[int, datetime]` | [ytdl\_inline\_bot/bot.py 73](https://github.com/magicxor/ytdl-inline-bot/blob/22164776/ytdl_inline_bot/bot.py#L73-L73) |
| VIP User | `VIP_USER_ID = int(os.environ.get("VIP_USER_ID", 282614687))` | [ytdl\_inline\_bot/bot.py 58](https://github.com/magicxor/ytdl-inline-bot/blob/22164776/ytdl_inline_bot/bot.py#L58-L58) |
| Window Duration | `RATE_LIMIT_WINDOW_MINUTES` | [ytdl\_inline\_bot/bot.py 70](https://github.com/magicxor/ytdl-inline-bot/blob/22164776/ytdl_inline_bot/bot.py#L70-L70) |
| Rate Check Logic | Lines 228-237, 369-374 | [ytdl\_inline\_bot/bot.py 228-237](https://github.com/magicxor/ytdl-inline-bot/blob/22164776/ytdl_inline_bot/bot.py#L228-L237) |

### Video Format Selection

The `get_best_video_audio_format()` function implements intelligent format selection based on size constraints and codec preferences:

| Priority | Criteria | Fallback Behavior |
| --- | --- | --- |
| 1st | `avc1` codec + `filesize <= MAX_VIDEO_SIZE` | Next priority if none found |
| 2nd | Any codec + `filesize <= MAX_VIDEO_SIZE` | Next priority if none found |
| 3rd | Smallest available format | Always selects something |

### Configuration System

The bot uses environment variables for all configuration with sensible defaults

## Dependencies and Technology Stack

The project leverages several key technologies managed through Poetry:

| Category | Package | Version | Purpose |
| --- | --- | --- | --- |
| Bot Framework | `aiogram` | ^3.20.0 | Telegram Bot API integration |
| Video Processing | `yt-dlp` | ^2025.5.22 | YouTube video downloading |
| HTTP Clients | `httpx`, `requests` | ^0.28.1, ^2.32.3 | Web requests and API calls |
| Web Scraping | `beautifulsoup4` | ^4.13.4 | HTML parsing for metadata |
| Security | `pycryptodome`, `certifi` | ^3.23.0, ^2025.4.26 | Encryption and SSL certificates |
| Development | `mypy` | ^1.15.0 | Static type checking |

The bot entry point is configured as `ytdlbot = "ytdl_inline_bot.bot:main"` in [pyproject.toml 31](https://github.com/magicxor/ytdl-inline-bot/blob/22164776/pyproject.toml#L31-L31) enabling direct execution via Poetry.

The bot implements multiple layers of error handling to ensure user experience remains smooth even when downloads fail:

1. **Retry Logic**: The `retry_operation()` function provides configurable retry attempts for network operations
2. **Placeholder Content**: Uses `PH_LOADING_VIDEO_URL` during processing and `ERR_LOADING_VIDEO_URL` for failures
3. **Thumbnail Fallback**: Extracts YouTube thumbnails using `extract_youtube_video_id()` when video downloads fail
4. **Graceful Degradation**: Falls back to error videos with predefined dimensions and duration
