from __future__ import annotations

import re

from bot.config import Config
from bot.data import command
from bot.data import format_msg
from bot.data import handle_message
from bot.message import Message

DIGITS_RE = re.compile(r'\d{1,4}\b')
PEP_RE = re.compile(fr'!pep(?P<pep_num>{DIGITS_RE.pattern})')


def _pep_msg(msg: Message, n_s: str) -> str:
    n = str(int(n_s)).zfill(4)
    return format_msg(msg, f'https://peps.python.org/pep-{n}/')


@command('!pep')
async def cmd_pep_no_arg(config: Config, msg: Message) -> str:
    _, _, rest = msg.msg.strip().partition(' ')
    digits_match = DIGITS_RE.match(rest)
    if digits_match is not None:
        return _pep_msg(msg, digits_match[0])
    else:
        return format_msg(msg, '!pep: expected argument <number>')


@handle_message(PEP_RE.pattern)
async def cmd_pep(config: Config, msg: Message) -> str:
    match = PEP_RE.match(msg.msg)
    assert match is not None
    return _pep_msg(msg, match['pep_num'])
