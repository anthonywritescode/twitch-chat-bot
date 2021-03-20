from __future__ import annotations

import asyncio
import os.path
from typing import NamedTuple

import aiohttp

from bot.util import atomic_open

EMOTE_CACHE = '.emote_cache'


def _emote_path(emote: str) -> str:
    return os.path.abspath(os.path.join(EMOTE_CACHE, f'{emote}.png'))


class EmotePosition(NamedTuple):
    start: int
    end: int
    emote: str


def parse_emote_info(s: str) -> list[EmotePosition]:
    if not s:
        return []

    ret = []
    for part in s.split('/'):
        emote, _, positions = part.partition(':')
        for pos in positions.split(','):
            start_s, _, end_s = pos.partition('-')
            ret.append(EmotePosition(int(start_s), int(end_s), emote))
    ret.sort()
    return ret


async def _ensure_downloaded(emote: str) -> None:
    emote_path = _emote_path(emote)
    if os.path.exists(emote_path):
        return

    os.makedirs(EMOTE_CACHE, exist_ok=True)

    dl_url = f'https://static-cdn.jtvnw.net/emoticons/v1/{emote}/1.0'
    async with aiohttp.ClientSession() as session:
        async with session.get(dl_url) as resp:
            data = await resp.read()

    with atomic_open(emote_path) as f:
        f.write(data)


async def download_all_emotes(emotes: list[EmotePosition]) -> None:
    unique_emotes = {emote.emote for emote in emotes}
    futures = [_ensure_downloaded(emote) for emote in unique_emotes]
    await asyncio.gather(*futures)


def replace_emotes(msg: str, emotes: list[EmotePosition]) -> str:
    parts = []
    pos = 0
    for emote in emotes:
        parts.append(msg[pos:emote.start])
        parts.append(
            f'\033}}ic#2;1;{_emote_path(emote.emote)}\000'
            f'\033}}ib\000##\033}}ie\000',
        )
        pos = emote.end + 1
    parts.append(msg[pos:])
    return ''.join(parts)
