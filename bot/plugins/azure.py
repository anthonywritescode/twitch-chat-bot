from __future__ import annotations

from bot.config import Config
from bot.data import command
from bot.data import format_msg
from bot.data import periodic_handler
from bot.message import Message


@periodic_handler(seconds=20 * 60)
@command('!coc', secret=True)
@command('!azure')
async def show_msft_coc(config: Config, msg: Message) -> str:
    return format_msg(
        msg,
        'this stream is sponsored by Microsoft Azure! - '
        'to learn more: https://aka.ms/AnthonyWrites_AzureFunction - '
        'code of conduct: https://github.com/microsoft/virtual-events',
    )
