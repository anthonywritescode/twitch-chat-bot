from __future__ import annotations

from typing import TypedDict

import aiohttp
import async_lru

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.message import Message


class UserData(TypedDict):
    channel_id: str
    channel_login: str
    pronoun_id: str
    alt_pronoun_id: str | None


class PronounData(TypedDict):
    name: str
    subject: str
    object: str
    singular: bool


async def _get_user_data(username: str) -> UserData | None:
    url = f'https://api.pronouns.alejo.io/v1/users/{username}'

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None

            return (await resp.json())


@async_lru.alru_cache(maxsize=1)
async def pronouns() -> dict[str, PronounData]:
    url = 'https://api.pronouns.alejo.io/v1/pronouns/'

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return (await resp.json())


async def _get_user_pronouns(username: str) -> tuple[str, str] | None:
    user_data = await _get_user_data(username)

    if user_data is None:
        return None

    pronoun_data = (await pronouns())[user_data['pronoun_id']]
    return (pronoun_data['subject'], pronoun_data['object'])


@command('!pronouns')
async def cmd_pronouns(config: Config, msg: Message) -> str:
    # TODO: handle display name
    username = msg.optional_user_arg.lower()
    pronouns = await _get_user_pronouns(username)

    if pronouns is None:
        return format_msg(msg, f'user not found {esc(username)}')

    (subj, obj) = pronouns
    return format_msg(msg, f'{username}\'s pronouns are: {subj}/{obj}')
