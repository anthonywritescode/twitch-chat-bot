from __future__ import annotations

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.message import Message


@command('!bongo')
async def cmd_bongo(config: Config, msg: Message) -> str:
    _, _, rest = msg.msg.partition(' ')
    rest = rest.strip()
    if rest:
        rest = f'{rest} '

    return format_msg(
        msg,
        f'awcBongo awcBongo awcBongo {esc(rest)}awcBongo awcBongo awcBongo',
    )
