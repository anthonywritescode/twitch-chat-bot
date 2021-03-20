from __future__ import annotations

import re
from typing import Match

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.permissions import is_moderator
from bot.permissions import optional_user_arg

USERNAME_RE = re.compile(r'\w+')


@command('!so', secret=True)
async def cmd_shoutout(config: Config, match: Match[str]) -> str | None:
    channel = optional_user_arg(match)
    user_match = USERNAME_RE.match(channel)
    if not is_moderator(match) and match['user'] != match['channel']:
        return format_msg(match, 'https://youtu.be/RfiQYRn7fBg')
    elif channel == match['user'] or user_match is None:
        return None
    user = user_match[0]
    return format_msg(
        match,
        f'you should check out https://twitch.tv/{esc(user)} !',
    )
