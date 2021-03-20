from __future__ import annotations

import random
import re
from typing import Match

from bot.config import Config
from bot.data import COMMANDS
from bot.data import esc
from bot.data import format_msg
from bot.data import handle_message


# XXX: this doesn't belong here, but ordering is important
@handle_message(
    '.*(is (this|that)|you us(e|ing)) (vim|nano)',
    flags=re.IGNORECASE,
)
async def msg_is_this_vim(config: Config, match: Match[str]) -> str | None:
    return await COMMANDS['!editor'](config, match)


@handle_message(
    r'.*\b(?P<word>nano|linux|windows|emacs|NT)\b', flags=re.IGNORECASE,
)
async def msg_gnu_please(config: Config, match: Match[str]) -> str | None:
    if random.randrange(0, 100) < 90:
        return None
    msg, word = match['msg'], match['word']
    query = re.search(f'gnu[/+]{word}', msg, flags=re.IGNORECASE)
    if query:
        return format_msg(match, f'YES! {query[0]}')
    else:
        return format_msg(match, f"Um please, it's GNU+{esc(word)}!")
