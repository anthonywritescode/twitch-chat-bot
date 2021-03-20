from __future__ import annotations

from typing import Match

from bot.config import Config
from bot.data import format_msg
from bot.data import handle_message


@handle_message(r'!pep[ ]?(?P<pep_num>\d{1,4})')
async def cmd_pep(config: Config, match: Match[str]) -> str:
    n = str(int(match['pep_num'])).zfill(4)
    return format_msg(match, f'https://www.python.org/dev/peps/pep-{n}/')
