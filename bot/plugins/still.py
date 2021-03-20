from __future__ import annotations

import datetime
import random
from typing import Match

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg


@command('!still')
async def cmd_still(config: Config, match: Match[str]) -> str:
    _, _, rest = match['msg'].partition(' ')
    year = datetime.date.today().year
    lol = random.choice(['LOL', 'LOLW', 'LMAO', 'NUUU'])
    return format_msg(match, f'{esc(rest)}, in {year} - {lol}!')
