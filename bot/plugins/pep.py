from typing import Match

from bot.data import handle_message
from bot.data import MessageResponse


@handle_message(r'!pep[ ]?(?P<pep_num>\d{1,4})')
def cmd_pep(match: Match[str]) -> MessageResponse:
    n = str(int(match['pep_num'])).zfill(4)
    return MessageResponse(match, f'https://www.python.org/dev/peps/pep-{n}/')
