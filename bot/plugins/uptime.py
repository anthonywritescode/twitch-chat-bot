import datetime
from typing import Match
from typing import Optional

import aiohttp

from bot.config import Config
from bot.data import command
from bot.data import MessageResponse
from bot.util import seconds_to_readable


class UptimeResponse(MessageResponse):
    def __init__(self, match: Match[str]) -> None:
        return super().__init__(match, '')

    async def __call__(self, config: Config) -> Optional[str]:
        url = f'https://api.twitch.tv/helix/streams?user_login={config.channel}'  # noqa: E501
        headers = {
            'Authorization': f'Bearer {config.oauth_token.split(":")[1]}',
            'Client-ID': config.client_id,
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                json_resp = await response.json()
                if not json_resp['data']:
                    self.msg_fmt = 'not currently streaming!'
                    return await super().__call__(config)
                start_time_s = json_resp['data'][0]['started_at']
                start_time = datetime.datetime.strptime(
                    start_time_s, '%Y-%m-%dT%H:%M:%SZ',
                )
                elapsed = (datetime.datetime.utcnow() - start_time).seconds

                self.msg_fmt = f'streaming for: {seconds_to_readable(elapsed)}'
                return await super().__call__(config)


@command('!uptime')
def cmd_uptime(match: Match[str]) -> UptimeResponse:
    return UptimeResponse(match)
