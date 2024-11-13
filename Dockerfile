FROM python:3-slim

# Environment variables
ENV MAX_VIDEO_SIZE=15728640
ENV MAX_AUDIO_SIZE=8388608
ENV VIP_USER_ID=282614687
ENV TELEGRAM_BOT_TOKEN=provide_your_bot_token_here
ENV ERR_LOADING_VIDEO_URL=https://magicxor.github.io/static/ytdl-inline-bot/error_v1.mp4
ENV ERR_THUMBNAIL_URL=https://magicxor.github.io/static/ytdl-inline-bot/error_v1.jpg
ENV ERR_VIDEO_WIDTH=640
ENV ERR_VIDEO_HEIGHT=480
ENV ERR_VIDEO_DURATION=5
ENV PH_LOADING_VIDEO_URL=https://magicxor.github.io/static/ytdl-inline-bot/loading_v2.mp4
ENV PH_THUMBNAIL_URL=https://magicxor.github.io/static/ytdl-inline-bot/loading_v1.jpg
ENV PH_VIDEO_WIDTH=1024
ENV PH_VIDEO_HEIGHT=576
ENV PH_VIDEO_DURATION=10
ENV MEDIA_CHAT_ID=-1002389753204
ENV RATE_LIMIT_WINDOW_MINUTES=1

RUN apt-get update && \
    apt-get upgrade -y && \
    python -m pip install --upgrade pip && \
    apt-get install -y curl ffmpeg && \
    mkdir /app

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

WORKDIR /app

COPY entrypoint.sh pyproject.toml poetry.lock* ./

RUN chmod +x entrypoint.sh

# Install dependencies without creating a virtual environment (since we're in a Docker container)
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# Copy the rest of the application code
COPY ytdl_inline_bot/ ./

CMD ["python", "bot.py"]
