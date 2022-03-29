from __future__ import annotations

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.message import Message


@command('!bonk')
async def cmd_bonk(config: Config, msg: Message) -> str:
    _, _, rest = msg.msg.partition(' ')
    rest = rest.strip() or 'marsha_socks'
    return format_msg(
        msg,
        f'awcBonk awcBonk awcBonk {esc(rest)} awcBonk awcBonk awcBonk',
    )
