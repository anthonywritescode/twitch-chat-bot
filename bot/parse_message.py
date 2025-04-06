from __future__ import annotations

import asyncio
import re
from collections.abc import Generator
from collections.abc import Mapping
from typing import NamedTuple

from bot.cheer import cheer_emotes
from bot.cheer import CheerInfo
from bot.emote import parse_emote_info
from bot.image_cache import download
from bot.image_cache import local_image_path
from bot.message import Message
from bot.message import parse_color


def terminology_image(url: str, *, width: int, height: int) -> str:
    parts = [f'\033}}ic#{width};{height};{url}\000']
    for _ in range(height):
        parts.append(f'\033}}ib\000{"#" * width}\033}}ie\000\n')
    return ''.join(parts).rstrip('\n')


class Emote(NamedTuple):
    url: str
    original: str


class Cheer(NamedTuple):
    url: str
    n: int
    color: str
    original: str


def _replace_cheer(
        s: str,
        cheer_info: Mapping[str, CheerInfo],
        cheer_regex: re.Pattern[str],
) -> Generator[str | Emote | Cheer]:
    pos = 0
    for match in cheer_regex.finditer(s):
        yield s[pos:match.start()]
        n = int(match[2])
        for tier in reversed(cheer_info[match[1].lower()].tiers):
            if n >= tier.min_bits:
                break
        yield Cheer(
            url=tier.image,
            n=n,
            color=tier.color,
            original=f'{match[1].lower()}{tier.min_bits}',
        )
        pos = match.end()
    yield s[pos:]


async def parse_message_parts(
        msg: Message,
        *,
        channel: str,
        oauth_token: str,
        client_id: str,
) -> list[str | Emote | Cheer]:
    emotes = parse_emote_info(msg.info['emotes'])

    parts: list[str | Emote | Cheer] = []
    pos = 0
    for emote in emotes:
        parts.append(msg.msg[pos:emote.start])
        parts.append(Emote(url=emote.download_url, original=emote.emote))
        pos = emote.end + 1
    parts.append(msg.msg[pos:])

    if 'bits' in msg.info:
        cheer_regex, cheer_info = await cheer_emotes(
            channel,
            oauth_token=oauth_token,
            client_id=client_id,
        )
        new_parts: list[str | Emote | Cheer] = []
        for part in parts:
            if isinstance(part, str):
                new_parts.extend(_replace_cheer(part, cheer_info, cheer_regex))
            else:
                new_parts.append(part)
        parts = new_parts

    return parts

_033 = '(?:033|x1b)'
_0_107 = '(?:10[0-7]|[0-9]?[0-9]?)'
_0_255 = '(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[0-9]?[0-9])'
_COLORIZE_ALLOWED = re.compile(
    fr'\\{_033}\[{_0_107}m|'
    fr'\\{_033}\[[34]8;5;{_0_255}m|'
    fr'\\{_033}\[[34]8;2;{_0_255};{_0_255};{_0_255}m',
)


def colorize(s: str) -> str:
    def replace_cb(m: re.Match[str]) -> str:
        return m[0].replace(r'\033', '\033').replace(r'\x1b', '\x1b')
    return f'{_COLORIZE_ALLOWED.sub(replace_cb, s)}\033[m'


async def parsed_to_terminology(
        parts: list[str | Emote | Cheer],
        *,
        big: bool,
) -> str:
    futures = []
    s_parts = []

    last_emote = -1
    for i, part in enumerate(parts):
        if isinstance(part, Emote):
            last_emote = i

    for i, part in enumerate(parts):
        if isinstance(part, str):
            s_parts.append(part)
        elif isinstance(part, Emote):
            url = local_image_path('emote', part.original)
            if big and i == last_emote:
                s_parts.append('\n')
                s_parts.append(terminology_image(url, width=11, height=6))
            else:
                s_parts.append(terminology_image(url, width=2, height=1))
            futures.append(download('emote', part.original, part.url))
        elif isinstance(part, Cheer):
            url = local_image_path('cheer', part.original)
            s_parts.append(terminology_image(url, width=2, height=1))
            r, g, b = parse_color(part.color)
            s_parts.append(f'\033[1m\033[38;2;{r};{g};{b}m{part.n}\033[m')
            futures.append(download('cheer', part.original, part.url))
        else:
            raise AssertionError(f'unexpected part: {part}')

    await asyncio.gather(*futures)
    return ''.join(s_parts)
