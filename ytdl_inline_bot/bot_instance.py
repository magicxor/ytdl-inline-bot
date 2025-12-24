#!/usr/bin/env python
"""Bot instance and dispatcher setup for the video downloader inline bot."""

from aiogram import Bot, Dispatcher, Router

from .config import TELEGRAM_BOT_TOKEN

# Create bot and dispatcher
bot: Bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp: Dispatcher = Dispatcher()
router: Router = Router()
dp.include_router(router)
