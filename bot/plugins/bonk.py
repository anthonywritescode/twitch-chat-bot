from __future__ import annotations

from typing import Match

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg


@command('!bonk')
async def cmd_bonk(config: Config, match: Match[str]) -> str:
    _, _, rest = match['msg'].partition(' ')
    rest = rest.strip() or 'marsha_socks'
    return format_msg(
        match,
        f'awcBonk awcBonk awcBonk {esc(rest)} awcBonk awcBonk awcBonk',
    )
