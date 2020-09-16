import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Match
from typing import Optional

import aiohttp
import async_lru
import humanize

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import MessageResponse
from bot.permissions import optional_user_arg


@async_lru.alru_cache(maxsize=32)
async def fetch_twitch_user(
        user: str,
        *,
        oauth_token: str,
        client_id: str
) -> Optional[List[Dict[str, Any]]]:
    url = 'https://api.twitch.tv/helix/users'
    params = [('login', user)]
    headers = {
        'Authorization': f'Bearer {oauth_token}',
        'Client-ID': client_id,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            json_resp = await resp.json()
            return json_resp.get('data')


async def fetch_twitch_user_follows(
        *,
        from_id: int,
        to_id: int,
        oauth_token: str,
        client_id: str
) -> Optional[List[Dict[str, Any]]]:
    url = 'https://api.twitch.tv/helix/users/follows'
    params = [('from_id', from_id), ('to_id', to_id)]
    headers = {
        'Authorization': f'Bearer {oauth_token}',
        'Client-ID': client_id,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            json_resp = await resp.json()
            return json_resp.get('data')


class FollowageResponse(MessageResponse):
    def __init__(self, match: Match[str], username: str) -> None:
        super().__init__(match, '')
        self.username = username

    async def __call__(self, config: Config) -> Optional[str]:
        token = config.oauth_token.split(':')[1]

        fetched_users = await fetch_twitch_user(
            config.channel,
            oauth_token=token,
            client_id=config.client_id,
        )
        assert fetched_users is not None
        me, = fetched_users

        fetched_users = await fetch_twitch_user(
            self.username,
            oauth_token=token,
            client_id=config.client_id,
        )
        if not fetched_users:
            self.msg_fmt = f'user {esc(self.username)} not found!'
            return await super().__call__(config)
        target_user, = fetched_users

        # if streamer wants to check the followage to their own channel
        if me['id'] == target_user['id']:
            self.msg_fmt = (
                f"@{esc(target_user['login'])}, you can't check !followage "
                f'to your own channel.  But I appreciate your curiosity!'
            )
            return await super().__call__(config)

        follow_age_results = await fetch_twitch_user_follows(
            from_id=target_user['id'],
            to_id=me['id'],
            oauth_token=token,
            client_id=config.client_id,
        )
        if not follow_age_results:
            self.msg_fmt = f'{esc(target_user["login"])} is not a follower!'
            return await super().__call__(config)
        follow_age, = follow_age_results

        now = datetime.datetime.utcnow()
        date_of_follow = datetime.datetime.fromisoformat(
            # twitch sends ISO date string with "Z" at the end,
            # which python's fromisoformat method does not like
            follow_age['followed_at'].rstrip('Z'),
        )
        delta = now - date_of_follow
        self.msg_fmt = (
            f'{esc(follow_age["from_name"])} has been following for '
            f'{esc(humanize.naturaldelta(delta))}!'
        )
        return await super().__call__(config)


# !followage -> valid, checks the caller
# !followage anthonywritescode -> valid, checks the user passed in payload
# !followage foo bar -> still valid, however the whole
# "foo bar" will be processed as a username
@command('!followage')
def cmd_followage(match: Match[str]) -> FollowageResponse:
    return FollowageResponse(match, optional_user_arg(match))
