from __future__ import annotations

from bot.config import Config
from bot.data import command
from bot.data import format_msg
from bot.message import Message


@command('!kevin', '!hovsater', secret=True)
async def cmd_kevin(config: Config, msg: Message) -> str:
    return format_msg(msg, "Kevin stop spending money you don't have")


@command('!isatisfied', secret=True)
async def cmd_isatisfied(config: Config, msg: Message) -> str:
    return format_msg(msg, "Keep spending money that Kevin doesn't have")
