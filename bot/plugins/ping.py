from typing import Match

from bot.data import esc
from bot.data import handle_message
from bot.data import MessageResponse


@handle_message('PING')
def msg_ping(match: Match[str]) -> MessageResponse:
    _, _, rest = match['msg'].partition(' ')
    return MessageResponse(match, f'PONG {esc(rest)}')
