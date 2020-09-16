import datetime
import random
from typing import Match

from bot.data import command
from bot.data import esc
from bot.data import MessageResponse


@command('!still')
def cmd_still(match: Match[str]) -> MessageResponse:
    _, _, rest = match['msg'].partition(' ')
    year = datetime.date.today().year
    lol = random.choice(['LOL', 'LOLW', 'LMAO', 'NUUU'])
    return MessageResponse(match, f'{esc(rest)}, in {year} - {lol}!')
