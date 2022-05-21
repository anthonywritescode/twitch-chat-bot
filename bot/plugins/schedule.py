from __future__ import annotations

from bot.config import Config
from bot.data import command
from bot.data import format_msg
from bot.message import Message


@command('!schedule')
async def cmd_schedule(config: Config, msg: Message) -> str:
    return format_msg(
        msg,
        "Monday evenings or Saturday at noon (EST) - See !twitter and !dicsord"
    )

