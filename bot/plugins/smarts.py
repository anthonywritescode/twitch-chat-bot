from __future__ import annotations

import functools
import re

from bot.config import Config
from bot.data import COMMANDS
from bot.data import handle_message
from bot.message import Message


def _reg(s: str) -> str:
    return fr".*what(['’]?s| is| does)?( this| that| the| your)? {s}\b"


async def _base(config: Config, msg: Message, *, cmd: str) -> str | None:
    return await COMMANDS[cmd](config, msg)


THINGS_TO_COMMANDS = (
    ('are (you|we) (doing|working on|making)', '!today'),
    ('babi', '!babi'),
    ('blue ball', '!bluething'),
    ('blue button', '!bluething'),
    ('blue thing', '!bluething'),
    ('code editor', '!editor'),
    ('color scheme', '!theme'),
    ('deadsnakes', '!deadsnakes'),
    ('distro', '!distro'),
    ('editor', '!editor'),
    ('keyboard', '!keyboard'),
    ('keypad', '!keyboard3'),
    ('os', '!os'),
    ('playlist', '!playlist'),
    ('project', '!project'),
    ('text editor', '!editor'),
    ('theme', '!theme'),
    ('trackball', '!bluething'),
)

for thing, command in THINGS_TO_COMMANDS:
    func = functools.partial(_base, cmd=command)
    handle_message(_reg(thing), flags=re.IGNORECASE)(func)
