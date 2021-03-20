from __future__ import annotations

import re
from typing import Match

from bot.config import Config
from bot.data import format_msg
from bot.data import handle_message


@handle_message(r'.*\bth[oi]nk(?:ing)?\b', flags=re.IGNORECASE)
async def msg_think(config: Config, match: Match[str]) -> str:
    return format_msg(match, 'awcPythonk ' * 5)
