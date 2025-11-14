# ytdl-inline-bot

[![Update Dependencies](https://github.com/magicxor/ytdl-inline-bot/actions/workflows/on_schedule_update_dependencies.yml/badge.svg)](https://github.com/magicxor/ytdl-inline-bot/actions/workflows/on_schedule_update_dependencies.yml)
[![master branch - check types, build, push](https://github.com/magicxor/ytdl-inline-bot/actions/workflows/on_master_push.yml/badge.svg)](https://github.com/magicxor/ytdl-inline-bot/actions/workflows/on_master_push.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/magicxor/ytdl-inline-bot)

A Telegram bot that allows users to download videos from YouTube via inline queries. It uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) under the hood to fetch and download videos.

https://github.com/user-attachments/assets/83826cf1-6486-4a7d-8631-6cdf44fac9d9

## Usage

```shell
docker run -i -t -d --restart=always --name=youtube_telegram_inline_bot -e TELEGRAM_BOT_TOKEN='YOUR_TOKEN' -e MEDIA_CHAT_ID=345347562 magicxor/ytdl-inline-bot:latest
```

## Environment variables

### Required
- `TELEGRAM_BOT_TOKEN` - Telegram bot token.
- `MEDIA_CHAT_ID` - chat ID where the bot will send temporary media files.

### Optional
- `MAX_VIDEO_SIZE` - target video size in bytes that should be downloaded. Default is 15 megabytes (15728640 bytes). In case the video is larger than this value, the bot will pick the smallest available format.
- `MAX_AUDIO_SIZE` - target audio size in bytes that should be downloaded. Default is 8 megabytes (8388608 bytes). In case the audio is larger than this value, the bot will pick the smallest available format.
- `MAX_TG_FILE_SIZE` - maximum file size in bytes that can be uploaded to Telegram. Default is 50 megabytes (52428800 bytes).
- `VIP_USER_ID` - user ID that is allowed to download videos without rate limit.
- `RATE_LIMIT_WINDOW_MINUTES` - rate limit window in minutes. Default is 1 minute.
- `PREFERRED_AUDIO_LANGUAGES` - comma-separated list of preferred audio languages. Default is "en-US,en,ru-RU,ru".
- `BOT_COOKIES_BASE64` - base64-encoded cookies for yt-dlp to bypass age restrictions or access private videos.
- `BOT_USER_AGENT` - custom User-Agent string for yt-dlp requests.

### Error video parameters
These parameters define the video shown when an error occurs:
- `ERR_LOADING_VIDEO_URL` - URL of the error video. Default is https://magicxor.github.io/static/ytdl-inline-bot/error_v1.mp4
- `ERR_THUMBNAIL_URL` - URL of the error video thumbnail. Default is https://magicxor.github.io/static/ytdl-inline-bot/error_v1.jpg
- `ERR_VIDEO_WIDTH` - width of the error video in pixels. Default is 640.
- `ERR_VIDEO_HEIGHT` - height of the error video in pixels. Default is 480.
- `ERR_VIDEO_DURATION` - duration of the error video in seconds. Default is 5.

### Placeholder video parameters
These parameters define the video shown while the requested video is being downloaded:
- `PH_LOADING_VIDEO_URL` - URL of the loading placeholder video. Default is https://magicxor.github.io/static/ytdl-inline-bot/loading_v2.mp4
- `PH_THUMBNAIL_URL` - URL of the loading video thumbnail. Default is https://magicxor.github.io/static/ytdl-inline-bot/loading_v1.jpg
- `PH_VIDEO_WIDTH` - width of the loading video in pixels. Default is 1024.
- `PH_VIDEO_HEIGHT` - height of the loading video in pixels. Default is 576.
- `PH_VIDEO_DURATION` - duration of the loading video in seconds. Default is 10.
