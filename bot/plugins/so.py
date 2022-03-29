from __future__ import annotations

import re

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.message import Message

USERNAME_RE = re.compile(r'\w+')


@command('!so', secret=True)
async def cmd_shoutout(config: Config, msg: Message) -> str | None:
    channel = msg.optional_user_arg
    user_match = USERNAME_RE.match(channel)
    if not msg.is_moderator and msg.name_key != config.channel:
        return format_msg(msg, 'https://youtu.be/RfiQYRn7fBg')
    elif channel == msg.name_key or user_match is None:
        return None
    user = user_match[0]
    return format_msg(
        msg,
        f'you should check out https://twitch.tv/{esc(user)} !',
    )
