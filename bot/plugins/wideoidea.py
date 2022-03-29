from __future__ import annotations

import os
import tempfile

from bot.config import Config
from bot.data import command
from bot.data import format_msg
from bot.message import Message
from bot.util import check_call


@command('!wideoidea', '!videoidea', secret=True)
async def cmd_videoidea(config: Config, msg: Message) -> str:
    if not msg.is_moderator and msg.name_key != config.channel:
        return format_msg(msg, 'https://youtu.be/RfiQYRn7fBg')
    _, _, rest = msg.msg.partition(' ')

    async def _git(*cmd: str) -> None:
        await check_call('git', '-C', tmpdir, *cmd)

    with tempfile.TemporaryDirectory() as tmpdir:
        await _git(
            'clone', '--depth=1', '--quiet',
            'git@github.com:asottile/scratch.wiki', '.',
        )
        ideas_file = os.path.join(tmpdir, 'anthony-explains-ideas.md')
        with open(ideas_file, 'rb+') as f:
            f.seek(-1, os.SEEK_END)
            c = f.read()
            if c != b'\n':
                f.write(b'\n')
            f.write(f'- {rest}\n'.encode())
        await _git('add', '.')
        await _git('commit', '-q', '-m', 'idea added by !videoidea')
        await _git('push', '-q', 'origin', 'HEAD')

    return format_msg(
        msg,
        'added! https://github.com/asottile/scratch/wiki/anthony-explains-ideas',  # noqa: E501
    )
