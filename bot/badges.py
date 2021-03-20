from __future__ import annotations

import asyncio
import collections
import os.path
import re
from typing import Mapping
from typing import NamedTuple

import aiohttp
import async_lru

from bot.twitch_api import fetch_twitch_user
from bot.util import atomic_open

BADGE_CACHE = '.badge_cache'


@async_lru.alru_cache(maxsize=1)
async def global_badges() -> Mapping[str, Mapping[str, str]]:
    url = 'https://badges.twitch.tv/v1/badges/global/display'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()

    return {
        badge: {
            version: dct['image_url_2x']
            for version, dct in v['versions'].items()
        }
        for badge, v in data['badge_sets'].items()
    }


@async_lru.alru_cache(maxsize=1)
async def channel_badges(
        username: str,
        *,
        oauth_token: str,
        client_id: str,
) -> Mapping[str, Mapping[str, str]]:
    user = await fetch_twitch_user(
        username,
        oauth_token=oauth_token,
        client_id=client_id,
    )
    assert user is not None

    url = f'https://badges.twitch.tv/v1/badges/channels/{user["id"]}/display'
    headers = {
        'Authorization': f'Bearer {oauth_token}',
        'Client-ID': client_id,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()

    return {
        badge: {
            version: dct['image_url_2x']
            for version, dct in v['versions'].items()
        }
        for badge, v in data['badge_sets'].items()
    }


def badges_plain_text(badges: str) -> str:
    ret = ''
    for s, reg in (
        ('\033[48;2;000;000;000m⚙\033[m', re.compile('^staff/')),
        ('\033[48;2;000;173;003m⚔\033[m', re.compile('^moderator/')),
        ('\033[48;2;224;005;185m♦\033[m', re.compile('^vip/')),
        ('\033[48;2;233;025;022m☞\033[m', re.compile('^broadcaster/')),
        ('\033[48;2;130;005;180m★\033[m', re.compile('^founder/')),
        ('\033[48;2;130;005;180m★\033[m', re.compile('^subscriber/')),
        ('\033[48;2;000;160;214m♕\033[m', re.compile('^premium/')),
        ('\033[48;2;089;057;154m♕\033[m', re.compile('^turbo/')),
        ('\033[48;2;230;186;072m◘\033[m', re.compile('^sub-gift-leader/')),
        ('\033[48;2;088;226;193m◘\033[m', re.compile('^sub-gifter/')),
        ('\033[48;2;183;125;029m♕\033[m', re.compile('^hype-train/')),
        ('\033[48;2;203;200;208m▴\033[m', re.compile('^bits/')),
        ('\033[48;2;230;186;072m♦\033[m', re.compile('^bits-leader/')),
        ('\033[48;2;145;070;255m☑\033[m', re.compile('^partner/')),
    ):
        for badge in badges.split(','):
            if reg.match(badge):
                ret += s
    return ret


class Badge(NamedTuple):
    badge: str
    version: str

    @property
    def fs_path(self) -> str:
        fname = f'{self.badge}_{self.version}.png'
        return os.path.abspath(os.path.join(BADGE_CACHE, fname))


def parse_badges(badges: str) -> list[Badge]:
    if not badges:
        return []

    ret = []
    for badge_s in badges.split(','):
        badge, version = badge_s.split('/', 1)
        ret.append(Badge(badge, version))
    return ret


async def _download_badge(
        badge: Badge,
        *,
        channel: str,
        oauth_token: str,
        client_id: str,
) -> None:
    if os.path.exists(badge.fs_path):
        return

    os.makedirs(BADGE_CACHE, exist_ok=True)

    badges_mapping = collections.ChainMap(
        await channel_badges(
            channel,
            oauth_token=oauth_token,
            client_id=client_id,
        ),
        await global_badges(),
    )
    url = badges_mapping[badge.badge][badge.version]

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()

    with atomic_open(badge.fs_path) as f:
        f.write(data)


async def download_all_badges(
        badges: list[Badge],
        *,
        channel: str,
        oauth_token: str,
        client_id: str,
) -> None:
    futures = [
        _download_badge(
            badge,
            channel=channel,
            oauth_token=oauth_token,
            client_id=client_id,
        )
        for badge in badges
    ]
    await asyncio.gather(*futures)


def badges_images(badges: list[Badge]) -> str:
    return ''.join(
        f'\033}}ic#2;1;{badge.fs_path}\000'
        f'\033}}ib\000##\033}}ie\000'
        for badge in badges
    )
