from __future__ import annotations

import re
from typing import Any
from typing import Mapping
from typing import NamedTuple

import aiohttp
import async_lru

from bot.twitch_api import fetch_twitch_user


class CheerTier(NamedTuple):
    min_bits: int
    color: str
    image: str

    @classmethod
    def from_dct(cls, dct: dict[str, Any]) -> CheerTier:
        return cls(
            min_bits=dct['min_bits'],
            color=dct['color'],
            image=dct['images']['dark']['animated']['2'],
        )


class CheerInfo(NamedTuple):
    prefix: str
    tiers: tuple[CheerTier, ...]

    @classmethod
    def from_dct(cls, dct: dict[str, Any]) -> CheerInfo:
        tiers = tuple(
            CheerTier.from_dct(tier_dct)
            for tier_dct in dct['tiers']
            if tier_dct['can_cheer'] or dct['prefix'].lower() == 'anon'
        )
        return cls(prefix=dct['prefix'].lower(), tiers=tiers)


@async_lru.alru_cache(maxsize=1)
async def cheer_emotes(
        channel: str,
        *,
        oauth_token: str,
        client_id: str,
) -> tuple[re.Pattern[str], Mapping[str, CheerInfo]]:
    user = await fetch_twitch_user(
        channel,
        oauth_token=oauth_token,
        client_id=client_id,
    )
    assert user is not None

    url = f'https://api.twitch.tv/helix/bits/cheermotes?broadcaster_id={user["id"]}'  # noqa: E501
    headers = {
        'Authorization': f'Bearer {oauth_token}',
        'Client-ID': client_id,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()

    infos = (CheerInfo.from_dct(dct) for dct in data['data'])
    cheer_info = {info.prefix: info for info in infos if info.tiers}
    joined = '|'.join(re.escape(k) for k in cheer_info)
    reg = re.compile(fr'(?:^|(?<=\s))({joined})(\d+)(?=\s|$)', re.ASCII | re.I)
    return reg, cheer_info
