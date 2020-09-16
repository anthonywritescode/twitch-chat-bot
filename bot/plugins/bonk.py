from typing import Match

from bot.data import command
from bot.data import esc
from bot.data import MessageResponse


@command('!bonk')
def cmd_bonk(match: Match[str]) -> MessageResponse:
    _, _, rest = match['msg'].partition(' ')
    rest = rest.strip() or 'Makayla_Fox'
    return MessageResponse(
        match,
        f'{esc(rest)}: '
        f'https://i.fluffy.cc/DM4QqzjR7wCpkGPwTl6zr907X50XgtBL.png',
    )
