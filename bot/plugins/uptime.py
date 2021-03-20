from __future__ import annotations

import datetime
from typing import Match

import aiohttp

from bot.config import Config
from bot.data import command
from bot.data import format_msg
from bot.util import seconds_to_readable


@command('!uptime')
async def cmd_uptime(config: Config, match: Match[str]) -> str:
    url = f'https://api.twitch.tv/helix/streams?user_login={config.channel}'
    headers = {
        'Authorization': f'Bearer {config.oauth_token_token}',
        'Client-ID': config.client_id,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            json_resp = await response.json()
            if not json_resp['data']:
                return format_msg(match, 'not currently streaming!')
            start_time_s = json_resp['data'][0]['started_at']
            start_time = datetime.datetime.strptime(
                start_time_s, '%Y-%m-%dT%H:%M:%SZ',
            )
            elapsed = (datetime.datetime.utcnow() - start_time).seconds

            readable_time = seconds_to_readable(elapsed)
            return format_msg(match, f'streaming for: {readable_time}')
