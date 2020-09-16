import random
import re
from typing import Match

from bot.data import COMMANDS
from bot.data import esc
from bot.data import handle_message
from bot.data import MessageResponse
from bot.data import Response


# XXX: this doesn't belong here, but ordering is important
@handle_message(
    '.*(is (this|that)|are you using) (vim|nano)',
    flags=re.IGNORECASE,
)
def msg_is_this_vim(match: Match[str]) -> Response:
    return COMMANDS['!editor'](match)


@handle_message(
    r'.*\b(?P<word>nano|linux|windows|emacs|NT)\b', flags=re.IGNORECASE,
)
def msg_gnu_please(match: Match[str]) -> Response:
    if random.randrange(0, 100) < 90:
        return Response()
    msg, word = match['msg'], match['word']
    query = re.search(f'gnu[/+]{word}', msg, flags=re.IGNORECASE)
    if query:
        return MessageResponse(match, f'YES! {query[0]}')
    else:
        return MessageResponse(match, f"Um please, it's GNU+{esc(word)}!")
