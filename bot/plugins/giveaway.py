from __future__ import annotations

import random
from typing import Match

import aiosqlite

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.permissions import is_moderator
from bot.permissions import is_subscriber


async def ensure_giveaway_tables_exist(db: aiosqlite.Connection) -> None:
    await db.execute(
        'CREATE TABLE IF NOT EXISTS giveaway ('
        '    active BIT NOT NULL,'
        '    PRIMARY KEY (active)'
        ')',
    )
    await db.execute(
        'CREATE TABLE IF NOT EXISTS giveaway_users (user TEXT NOT NULL)',
    )
    await db.commit()


@command('!giveawaystart', secret=True)
async def givewawaystart(config: Config, match: Match[str]) -> str | None:
    if not is_moderator(match) and match['user'] != match['channel']:
        return None

    async with aiosqlite.connect('db.db') as db:
        await ensure_giveaway_tables_exist(db)

        await db.execute('INSERT OR REPLACE INTO giveaway VALUES (1)')
        await db.commit()

    return format_msg(
        match,
        'giveaway started!  use !giveaway to enter (subs only)',
    )


@command('!giveaway', secret=True)
async def giveaway(config: Config, match: Match[str]) -> str:
    if not is_subscriber(match):
        return format_msg(match, 'not a subscriber! subscribe to enter')

    async with aiosqlite.connect('db.db') as db:
        await ensure_giveaway_tables_exist(db)

        async with db.execute('SELECT active FROM giveaway') as cursor:
            row = await cursor.fetchone()
            if row is None or not row[0]:
                return format_msg(match, 'no current giveaway active!')

        await ensure_giveaway_tables_exist(db)
        query = 'INSERT OR REPLACE INTO giveaway_users VALUES (?)'
        await db.execute(query, (match['user'],))
        await db.commit()

    return format_msg(match, f'{esc(match["user"])} has been entered!')


@command('!giveawayend', secret=True)
async def giveawayend(config: Config, match: Match[str]) -> str | None:
    if not is_moderator(match) and match['user'] != match['channel']:
        return None

    async with aiosqlite.connect('db.db') as db:
        await ensure_giveaway_tables_exist(db)

        async with db.execute('SELECT active FROM giveaway') as cursor:
            row = await cursor.fetchone()
            if row is None or not row[0]:
                return format_msg(match, 'no current giveaway active!')

        query = 'SELECT user FROM giveaway_users'
        async with db.execute(query) as cursor:
            users = [user for user, in await cursor.fetchall()]

        if users:
            await db.execute('INSERT OR REPLACE INTO giveaway VALUES (0)')
            await db.commit()

        await db.execute('DROP TABLE giveaway_users')
        await db.execute('DROP TABLE giveaway')
        await db.commit()

    if not users:
        return format_msg(match, 'no users entered giveaway!')

    winner = random.choice(users)
    return format_msg(match, f'!giveaway winner is {esc(winner)}')
