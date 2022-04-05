from __future__ import annotations

from bot.config import Config
from bot.data import esc
from bot.data import format_msg
from bot.data import handle_message
from bot.message import Message


@handle_message('PING')
async def msg_ping(config: Config, msg: Message) -> str:
    _, _, rest = msg.msg.partition(' ')
    return format_msg(msg, f'PONG {esc(rest)}')
