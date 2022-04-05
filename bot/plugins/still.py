from __future__ import annotations

import datetime
import random

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.message import Message


@command('!still')
async def cmd_still(config: Config, msg: Message) -> str:
    _, _, rest = msg.msg.partition(' ')
    year = datetime.date.today().year
    lol = random.choice(['LOL', 'LOLW', 'LMAO', 'NUUU'])
    return format_msg(msg, f'{esc(rest)}, in {year} - {lol}!')
