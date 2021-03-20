from __future__ import annotations

from typing import Match

import pyjokes

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg


@command('!joke')
async def cmd_joke(config: Config, match: Match[str]) -> str:
    return format_msg(match, esc(pyjokes.get_joke()))
