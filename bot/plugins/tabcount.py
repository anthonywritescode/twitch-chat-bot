from __future__ import annotations

import json
import os

import lz4.block

from bot.config import Config
from bot.data import command
from bot.data import format_msg
from bot.message import Message


@command('!tabcount')
async def cmd_tabcount(config: Config, msg: Message) -> str:
    firefox_home = os.path.expanduser('~/.mozilla/firefox/')
    tabcount = 0
    for (path, _, files) in os.walk(firefox_home):
        if 'sessionstore' in path:
            session = os.path.join(firefox_home, path, 'recovery.jsonlz4')
            with open(session, 'rb') as f:
                data = json.loads(lz4.block.decompress(f.read()[8:]))
                for windows in data['windows']:
                    for tab in windows['tabs']:
                        tabcount += 1
    return format_msg(msg, f'{tabcount} tabs open!')
