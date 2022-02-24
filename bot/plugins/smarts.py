from __future__ import annotations

import functools
import re
from typing import Match

from bot.config import Config
from bot.data import COMMANDS
from bot.data import handle_message


def _reg(s: str) -> str:
    return fr".*what('s| is)?( this| that)? {s}"


async def _base(config: Config, match: Match[str], *, cmd: str) -> str | None:
    return await COMMANDS[cmd](config, match)


THINGS_TO_COMMANDS = (
    ('keyboard', '!keyboard'),
    ('keypad', '!keyboard3'),
    ('trackball', '!bluething'),
    ('blue thing', '!bluething'),
)

for thing, command in THINGS_TO_COMMANDS:
    func = functools.partial(_base, cmd=command)
    handle_message(_reg(thing), flags=re.IGNORECASE)(func)
