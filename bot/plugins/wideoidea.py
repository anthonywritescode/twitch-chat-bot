from __future__ import annotations

import os
import tempfile
from typing import Match

from bot.config import Config
from bot.data import command
from bot.data import format_msg
from bot.permissions import is_moderator
from bot.util import check_call


@command('!wideoidea', '!videoidea', secret=True)
async def cmd_videoidea(config: Config, match: Match[str]) -> str:
    if not is_moderator(match) and match['user'] != match['channel']:
        return format_msg(match, 'https://youtu.be/RfiQYRn7fBg')
    _, _, rest = match['msg'].partition(' ')

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
        match,
        'added! https://github.com/asottile/scratch/wiki/anthony-explains-ideas',  # noqa: E501
    )
