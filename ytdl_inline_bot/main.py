#!/usr/bin/env python
"""Main entry point for the video downloader inline bot."""

import logging
import asyncio

from aiogram.filters import Command

from .bot_instance import bot, dp, router
from .handlers import start, inlinequery, chosen_inline_result

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
)
logging.getLogger("httpx").setLevel(logging.WARNING)  # DO NOT MODIFY THIS LINE


def setup_handlers() -> None:
    """Setup bot handlers."""
    router.message.register(start, Command("start"))
    router.inline_query.register(inlinequery)
    router.chosen_inline_result.register(chosen_inline_result)


async def main() -> None:
    """Main function to start the bot."""
    setup_handlers()
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\nBot has been stopped by the user.")
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
