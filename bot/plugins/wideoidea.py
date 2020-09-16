import asyncio.subprocess
import os
import tempfile
from typing import Match
from typing import Optional

from bot.config import Config
from bot.data import command
from bot.data import MessageResponse
from bot.permissions import is_moderator


async def _check_call(*cmd: str) -> None:
    proc = await asyncio.subprocess.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    if proc.returncode != 0:
        raise ValueError(cmd, proc.returncode)


class VideoIdeaResponse(MessageResponse):
    def __init__(self, match: Match[str], videoidea: str) -> None:
        super().__init__(
            match,
            'added! https://github.com/asottile/scratch/wiki/anthony-explains-ideas',  # noqa: E501
        )
        self.videoidea = videoidea

    async def __call__(self, config: Config) -> Optional[str]:
        async def _git(*cmd: str) -> None:
            await _check_call('git', '-C', tmpdir, *cmd)

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
                f.write(f'- {self.videoidea}\n'.encode())
            await _git('add', '.')
            await _git('commit', '-q', '-m', 'idea added by !videoidea')
            await _git('push', '-q', 'origin', 'HEAD')
        return await super().__call__(config)


@command('!wideoidea', '!videoidea')
def cmd_videoidea(match: Match[str]) -> MessageResponse:
    if not is_moderator(match) and match['user'] != match['channel']:
        return MessageResponse(match, 'https://youtu.be/RfiQYRn7fBg')
    _, _, rest = match['msg'].partition(' ')
    return VideoIdeaResponse(match, rest)
