import re
from typing import Match

from bot.data import handle_message
from bot.data import MessageResponse


@handle_message(r'.*\bth[oi]nk(?:ing)?\b', flags=re.IGNORECASE)
def msg_think(match: Match[str]) -> MessageResponse:
    return MessageResponse(match, 'awcPythonk ' * 5)
