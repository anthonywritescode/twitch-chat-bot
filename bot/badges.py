from __future__ import annotations

import asyncio
import re
from typing import Mapping
from typing import NamedTuple

import aiohttp
import async_lru

from bot.image_cache import download
from bot.image_cache import local_image_path
from bot.twitch_api import fetch_twitch_user


@async_lru.alru_cache(maxsize=1)
async def global_badges(
        *,
        oauth_token: str,
        client_id: str,
) -> Mapping[str, Mapping[str, str]]:
    url = 'https://api.twitch.tv/helix/chat/badges/global'
    headers = {
        'Authorization': f'Bearer {oauth_token}',
        'Client-ID': client_id,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()

    return {
        v['set_id']: {
            version['id']: version['image_url_2x']
            for version in v['versions']
        }
        for v in data['data']
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

    url = f'https://api.twitch.tv/helix/chat/badges?broadcaster_id={user["id"]}'  # noqa: E501
    headers = {
        'Authorization': f'Bearer {oauth_token}',
        'Client-ID': client_id,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()

    return {
        v['set_id']: {
            version['id']: version['image_url_2x']
            for version in v['versions']
        }
        for v in data['data']
    }


@async_lru.alru_cache(maxsize=1)
async def all_badges(
        username: str,
        *,
        oauth_token: str,
        client_id: str,
) -> Mapping[str, Mapping[str, str]]:
    return {
        **await global_badges(oauth_token=oauth_token, client_id=client_id),
        **await channel_badges(
            username,
            oauth_token=oauth_token,
            client_id=client_id,
        ),
    }


def badges_plain_text(badges: tuple[str, ...]) -> str:
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
        for badge in badges:
            if reg.match(badge):
                ret += s
    return ret


class Badge(NamedTuple):
    badge: str
    version: str

    @property
    def local_filename(self) -> str:
        return f'{self.badge}_{self.version}.png'

    @property
    def fs_path(self) -> str:
        return local_image_path('badge', self.local_filename)


def parse_badges(badges: str) -> list[Badge]:
    if not badges:
        return []

    ret = []
    for badge_s in badges.split(','):
        badge, version = badge_s.split('/', 1)
        ret.append(Badge(badge, version))
    return ret


async def download_all_badges(
        badges: list[Badge],
        *,
        channel: str,
        oauth_token: str,
        client_id: str,
) -> None:
    badges_mapping = await all_badges(
        channel,
        oauth_token=oauth_token,
        client_id=client_id,
    )
    futures = [
        download(
            subtype='badge',
            name=badge.local_filename,
            url=badges_mapping[badge.badge][badge.version],
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
