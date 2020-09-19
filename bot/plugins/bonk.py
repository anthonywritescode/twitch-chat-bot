from typing import Match

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg


@command('!bonk')
async def cmd_bonk(config: Config, match: Match[str]) -> str:
    _, _, rest = match['msg'].partition(' ')
    rest = rest.strip() or 'Makayla_Fox'
    return format_msg(
        match,
        f'{esc(rest)}: '
        f'https://i.fluffy.cc/DM4QqzjR7wCpkGPwTl6zr907X50XgtBL.png',
    )
