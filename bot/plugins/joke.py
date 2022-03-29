from __future__ import annotations

import pyjokes

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.message import Message


@command('!joke', '!yoke')
async def cmd_joke(config: Config, msg: Message) -> str:
    return format_msg(msg, esc(pyjokes.get_joke()))
