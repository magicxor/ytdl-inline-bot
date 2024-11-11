# ytdl-inline-bot

A Telegram bot that allows users to download videos from YouTube via inline queries.

https://github.com/user-attachments/assets/83826cf1-6486-4a7d-8631-6cdf44fac9d9

## Usage

```shell
docker run -i -t -d --restart=always --name=youtube_telegram_inline_bot -e TELEGRAM_BOT_TOKEN='YOUR_TOKEN' -e MEDIA_CHAT_ID=345347562 magicxor/ytdl-inline-bot:latest
```

## Environment variables

- `MAX_VIDEO_SIZE` - target video size in bytes that should be downloaded. Default is 15 megabytes (15728640 bytes). In case the video is larger than this value, the bot will pick the smallest available format.
- `MAX_AUDIO_SIZE` - target audio size in bytes that should be downloaded. Default is 8 megabytes (8388608 bytes). In case the audio is larger than this value, the bot will pick the smallest available format.
- `VIP_USER_ID` - user ID that is allowed to download videos without rate limit.
- `TELEGRAM_BOT_TOKEN` - Telegram bot token.
- `ERR_*` - parameters of a video that will be shown in case of an error.
- `PH_*` - parameters of a video that will be shown while the requested video is being downloaded.
- `MEDIA_CHAT_ID` - chat ID where the bot will send temporary media files.
- `RATE_LIMIT_WINDOW_MINUTES` - rate limit window in minutes. Default is 1 minute.
