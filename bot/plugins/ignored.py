from __future__ import annotations

from bot.config import Config
from bot.data import command
from bot.message import Message


@command('!ftlwiki', secret=True)
async def cmd_still(config: Config, msg: Message) -> None:
    pass
