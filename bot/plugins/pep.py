from __future__ import annotations

import re
from typing import Match

from bot.config import Config
from bot.data import command
from bot.data import format_msg
from bot.data import handle_message

DIGITS_RE = re.compile(r'\d{1,4}\b')


def _pep_msg(match: Match[str], n_s: str) -> str:
    n = str(int(n_s)).zfill(4)
    return format_msg(match, f'https://peps.python.org/pep-{n}/')


@command('!pep')
async def cmd_pep_no_arg(config: Config, match: Match[str]) -> str:
    _, _, rest = match['msg'].strip().partition(' ')
    digits_match = DIGITS_RE.match(rest)
    if digits_match is not None:
        return _pep_msg(match, digits_match[0])
    else:
        return format_msg(match, '!pep: expected argument <number>')


@handle_message(fr'!pep(?P<pep_num>{DIGITS_RE.pattern})')
async def cmd_pep(config: Config, match: Match[str]) -> str:
    return _pep_msg(match, match['pep_num'])
