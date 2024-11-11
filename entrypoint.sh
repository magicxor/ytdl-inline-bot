#!/bin/bash

set -e

# Function to gracefully stop the bot, upgrade dependencies, and restart
restart_bot() {
    echo "Stopping the bot..."
    pkill -f bot.py || true

    echo "Upgrading pip and yt-dlp..."
    python -m pip install --upgrade pip
    pip install yt-dlp --upgrade

    echo "Restarting the bot..."
    python bot.py &
}

# Start the bot initially
echo "Starting the bot..."
python bot.py &

# Schedule daily restart at midnight
while true; do
    # Get current time in seconds since epoch
    current_time=$(date +%s)
    # Calculate seconds until midnight
    midnight=$(date -d "tomorrow 00:00:00" +%s)
    sleep_seconds=$((midnight - current_time))

    echo "Sleeping until midnight (about $((sleep_seconds / 60)) minutes)..."
    sleep "$sleep_seconds"

    # Perform the restart and upgrade
    restart_bot
done
