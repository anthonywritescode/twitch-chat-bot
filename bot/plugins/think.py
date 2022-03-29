from __future__ import annotations

import random
import re

from bot.config import Config
from bot.data import format_msg
from bot.data import handle_message
from bot.message import Message


@handle_message(r'.*\bth[oi]nk(?:ing)?\b', flags=re.IGNORECASE)
async def msg_think(config: Config, msg: Message) -> str | None:
    if random.randrange(0, 100) < 90:
        return None
    return format_msg(msg, 'awcPythonk ' * 5)
