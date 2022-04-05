from __future__ import annotations

import random
import re

from bot.config import Config
from bot.data import COMMANDS
from bot.data import esc
from bot.data import format_msg
from bot.data import handle_message
from bot.message import Message

GNU_RE = re.compile(
    r'.*\b(?P<word>nano|linux|windows|emacs|NT)\b', flags=re.IGNORECASE,
)

# XXX: this doesn't belong here, but ordering is important


@handle_message(
    '.*(why|is (this|that)|you us(e|ing)|instead of) (vim|nano)',
    flags=re.IGNORECASE,
)
async def msg_is_this_vim(config: Config, msg: Message) -> str | None:
    return await COMMANDS['!editor'](config, msg)


@handle_message(GNU_RE.pattern, flags=re.IGNORECASE)
async def msg_gnu_please(config: Config, msg: Message) -> str | None:
    if random.randrange(0, 100) < 90:
        return None

    match = GNU_RE.match(msg.msg)
    assert match is not None
    word = match['word']
    query = re.search(f'gnu[/+]{word}', msg.msg, flags=re.IGNORECASE)
    if query:
        return format_msg(msg, f'YES! {query[0]}')
    else:
        return format_msg(msg, f"Um please, it's GNU+{esc(word)}!")
