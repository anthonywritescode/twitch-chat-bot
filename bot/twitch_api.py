from __future__ import annotations

from typing import Any

import aiohttp
import async_lru


@async_lru.alru_cache(maxsize=32)
async def fetch_twitch_user(
        username: str,
        *,
        oauth_token: str,
        client_id: str,
) -> dict[str, Any] | None:
    url = f'https://api.twitch.tv/helix/users?login={username}'
    headers = {
        'Authorization': f'Bearer {oauth_token}',
        'Client-ID': client_id,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            json_resp = await resp.json()
            users = json_resp.get('data')
            if users:
                user, = users
                return user
            else:
                return None
