from __future__ import annotations

import datetime
from typing import Any
from typing import Match

import aiohttp
import humanize

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.permissions import optional_user_arg
from bot.twitch_api import fetch_twitch_user


async def fetch_twitch_user_follows(
        *,
        from_id: int,
        to_id: int,
        oauth_token: str,
        client_id: str,
) -> list[dict[str, Any]] | None:
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


# !followage -> valid, checks the caller
# !followage anthonywritescode -> valid, checks the user passed in payload
# !followage foo bar -> still valid, however the whole
# "foo bar" will be processed as a username
@command('!followage')
async def cmd_followage(config: Config, match: Match[str]) -> str:
    username = optional_user_arg(match)

    me = await fetch_twitch_user(
        config.channel,
        oauth_token=config.oauth_token_token,
        client_id=config.client_id,
    )
    assert me is not None

    target_user = await fetch_twitch_user(
        username,
        oauth_token=config.oauth_token_token,
        client_id=config.client_id,
    )
    if target_user is None:
        return format_msg(match, f'user {esc(username)} not found!')

    # if streamer wants to check the followage to their own channel
    if me['id'] == target_user['id']:
        return format_msg(
            match,
            f"@{esc(target_user['login'])}, you can't check !followage "
            f'to your own channel.  But I appreciate your curiosity!',
        )

    follow_age_results = await fetch_twitch_user_follows(
        from_id=target_user['id'],
        to_id=me['id'],
        oauth_token=config.oauth_token_token,
        client_id=config.client_id,
    )
    if not follow_age_results:
        return format_msg(
            match,
            f'{esc(target_user["login"])} is not a follower!',
        )
    follow_age, = follow_age_results

    now = datetime.datetime.utcnow()
    date_of_follow = datetime.datetime.fromisoformat(
        # twitch sends ISO date string with "Z" at the end,
        # which python's fromisoformat method does not like
        follow_age['followed_at'].rstrip('Z'),
    )
    delta = now - date_of_follow
    return format_msg(
        match,
        f'{esc(follow_age["from_name"])} has been following for '
        f'{esc(humanize.naturaldelta(delta))}!',
    )
