import re
from typing import Match

from bot.data import command
from bot.data import esc
from bot.data import MessageResponse
from bot.data import Response
from bot.permissions import is_moderator
from bot.permissions import optional_user_arg

USERNAME_RE = re.compile(r'\w+')


@command('!so', secret=True)
def cmd_shoutout(match: Match[str]) -> Response:
    channel = optional_user_arg(match)
    user_match = USERNAME_RE.match(channel)
    if not is_moderator(match) and match['user'] != match['channel']:
        return MessageResponse(match, 'https://youtu.be/RfiQYRn7fBg')
    elif channel == match['user'] or user_match is None:
        return Response()
    user = user_match[0]
    return MessageResponse(
        match,
        f'you should check out https://twitch.tv/{esc(user)} !',
    )
