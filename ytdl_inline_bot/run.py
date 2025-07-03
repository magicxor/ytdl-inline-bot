#!/usr/bin/env python
"""Entry point script for running the YouTube downloader inline bot."""

import asyncio
from .main import main

if __name__ == '__main__':
    asyncio.run(main())
