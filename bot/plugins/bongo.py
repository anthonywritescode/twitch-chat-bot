from __future__ import annotations

from typing import Match

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg


@command('!bongo')
async def cmd_bongo(config: Config, match: Match[str]) -> str:
    _, _, rest = match['msg'].partition(' ')
    rest = rest.strip()
    if rest:
        rest = f'{rest} '

    return format_msg(
        match,
        f'awcBongo awcBongo awcBongo {esc(rest)}awcBongo awcBongo awcBongo',
    )
