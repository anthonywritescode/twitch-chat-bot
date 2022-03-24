from __future__ import annotations

import os
import random
from typing import Match

from bot.config import Config
from bot.data import command
from bot.data import format_msg

NO_QUOTES = '@{} sorry, there are no quotes :('

FILES_WITH_NO_QUOTES = set()


@command('!quote')
async def cmd_quote(config: Config, match: Match[str]) -> str:
    filenames = [
        filename for filename in os.listdir('logs')
        if filename not in FILES_WITH_NO_QUOTES
    ]
    for filename in random.sample(filenames, len(filenames)):
        full_filename = os.path.join('logs', filename)
        quote = random_quote(config, match, full_filename)
        if quote:
            return format_msg(match, f'"{quote}"')
        FILES_WITH_NO_QUOTES.add(filename)
    return format_msg(match, NO_QUOTES.format(match['user']))


def random_quote(config: Config, match: Match[str], filename: str) -> str:
    with open(filename) as f:
        user_logs = [
            log for log in f.readlines()
            if username(log) != config.username
        ]
        messages = [message(log) for log in user_logs]
        quotes = [
            message for message in messages
            if not message.startswith('!')
        ]
        if not quotes:
            return ''
        return random.choice(quotes)


def username(log: str) -> str:
    return log[log.index('<') + 1: log.index('>')]


def message(log: str) -> str:
    return log.partition(' ')[2][:-1]
