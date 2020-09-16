from typing import Match

import pyjokes

from bot.data import command
from bot.data import esc
from bot.data import MessageResponse


@command('!joke')
def cmd_joke(match: Match[str]) -> MessageResponse:
    return MessageResponse(match, esc(pyjokes.get_joke()))
