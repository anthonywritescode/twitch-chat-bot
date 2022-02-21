from __future__ import annotations

import re
from typing import Match

from bot.config import Config
from bot.data import COMMANDS
from bot.data import handle_message


@handle_message(
    '.*what keyboard',
    flags=re.IGNORECASE,
)
async def msg_what_keyboard(config: Config, match: Match[str]) -> str | None:
    return await COMMANDS['!keyboard'](config, match)


@handle_message(
    '.*what keypad',
    flags=re.IGNORECASE,
)
async def msg_what_keypad(config: Config, match: Match[str]) -> str | None:
    return await COMMANDS['!keyboard3'](config, match)


@handle_message(
    '.*what trackball',
    flags=re.IGNORECASE,
)
async def msg_what_trackball(config: Config, match: Match[str]) -> str | None:
    return await COMMANDS['!bluething'](config, match)
