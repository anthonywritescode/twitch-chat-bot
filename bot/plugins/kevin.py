from __future__ import annotations

from typing import Match

from bot.config import Config
from bot.data import command
from bot.data import format_msg


@command('!kevinsjoberg', secret=True)
async def cmd_kevin(config: Config, match: Match[str]) -> str:
    return format_msg(match, "Kevin stop spending money you don't have")


@command('!isatisfied', secret=True)
async def cmd_isatisfied(config: Config, match: Match[str]) -> str:
    return format_msg(
        match,
        "Keep spending money that kevinsjoberg doesn't have",
    )
