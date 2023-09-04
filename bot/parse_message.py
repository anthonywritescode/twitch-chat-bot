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

TERMINOLOGY_IMAGE = '\033}}ic#2;1;{url}\000\033}}ib\000##\033}}ie\000'


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
) -> Generator[str | Emote | Cheer, None, None]:
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


async def parsed_to_terminology(parts: list[str | Emote | Cheer]) -> str:
    futures = []
    s_parts = []

    for part in parts:
        if isinstance(part, str):
            s_parts.append(part)
        elif isinstance(part, Emote):
            url = local_image_path('emote', part.original)
            s_parts.append(TERMINOLOGY_IMAGE.format(url=url))
            futures.append(download('emote', part.original, part.url))
        elif isinstance(part, Cheer):
            url = local_image_path('cheer', part.original)
            s_parts.append(TERMINOLOGY_IMAGE.format(url=url))
            r, g, b = parse_color(part.color)
            s_parts.append(f'\033[1m\033[38;2;{r};{g};{b}m{part.n}\033[m')
            futures.append(download('cheer', part.original, part.url))
        else:
            raise AssertionError(f'unexpected part: {part}')

    await asyncio.gather(*futures)
    return ''.join(s_parts)
