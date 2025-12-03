from __future__ import annotations

from typing import TypedDict

import aiohttp
import async_lru

from bot.config import Config
from bot.data import command
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

            json_resp = await resp.json()
            return json_resp


@async_lru.alru_cache(maxsize=1)
async def pronouns() -> dict[str, PronounData]:
    '''
    Database of all pronouns, with their various forms.
    '''

    url = 'https://api.pronouns.alejo.io/v1/pronouns/'

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            json_resp = await resp.json()
            return json_resp


async def _get_user_pronouns(username: str) -> tuple[str, str] | None:
    '''
    Get the pronouns of the user given their `username`.

    The returned value is a pair `(main subject/alt subject)`
    if the user has alternative pronouns,
    `(main subject/main object)` if they don't, and `None` if
    their username is not known to the pronouns service.

    Note: pronouns are in English, and put in lowercase.
    '''

    user_data = await _get_user_data(username)

    if user_data is None:
        return None

    all_pronouns = await pronouns()
    main_pronoun_data = all_pronouns[user_data['pronoun_id']]
    maybe_alt_pronoun_id = user_data['alt_pronoun_id']

    # first is always main subject
    first = main_pronoun_data['subject'].casefold()

    if maybe_alt_pronoun_id is not None:
        # second is alt subject if they have alt pronouns
        second = all_pronouns[maybe_alt_pronoun_id]['subject'].casefold()
    else:
        # second is main object if they don't
        second = main_pronoun_data['object'].casefold()

    return (first, second)


@command('!pronouns')
async def cmd_pronouns(config: Config, msg: Message) -> str:
    # TODO: handle display name
    username = msg.optional_user_arg.lower()
    pronouns = await _get_user_pronouns(username)

    if pronouns is None:
        return format_msg(msg, f'user not found: {username}')

    (subj, obj) = pronouns
    return format_msg(msg, f"{username}'s pronouns are: {subj}/{obj}")
