from __future__ import annotations

from typing import Match

from bot.config import Config
from bot.data import esc
from bot.data import format_msg
from bot.data import handle_message


@handle_message('PING')
async def msg_ping(config: Config, match: Match[str]) -> str:
    _, _, rest = match['msg'].partition(' ')
    return format_msg(match, f'PONG {esc(rest)}')
