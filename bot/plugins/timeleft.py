from __future__ import annotations

import datetime
from typing import Match

from bot.config import Config
from bot.data import command
from bot.data import format_msg
from bot.util import seconds_to_readable


@command('!12hour')
async def cmd_12hour(config: Config, match: Match[str]) -> str:
    return format_msg(
        match,
        'MSR974 cashed in the channel points, so here we are... '
        'see also !timeleft',
    )


@command('!timeleft', '!downtime', '!timeright')
async def cmd_timeleft(config: Config, match: Match[str]) -> str:
    end_time = datetime.datetime(2022, 4, 2, 22, 0)
    if datetime.datetime.now() > end_time:
        return format_msg(match, 'done!!!')
    else:
        remaining = (end_time - datetime.datetime.now()).seconds
        msg = f'{seconds_to_readable(remaining)} left in the stream!'
        return format_msg(match, msg)
