from __future__ import annotations

import random

import aiosqlite

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.message import Message


async def ensure_giveaway_tables_exist(db: aiosqlite.Connection) -> None:
    await db.execute(
        'CREATE TABLE IF NOT EXISTS giveaway ('
        '    active BIT NOT NULL,'
        '    PRIMARY KEY (active)'
        ')',
    )
    await db.execute(
        'CREATE TABLE IF NOT EXISTS giveaway_users ('
        '    user TEXT NOT NULL,'
        '    PRIMARY KEY (user)'
        ')',
    )
    await db.commit()


@command('!giveawaystart', secret=True)
async def givewawaystart(config: Config, msg: Message) -> str | None:
    if not msg.is_moderator and msg.name_key != config.channel:
        return None

    async with aiosqlite.connect('db.db') as db:
        await ensure_giveaway_tables_exist(db)

        await db.execute('INSERT OR REPLACE INTO giveaway VALUES (1)')
        await db.commit()

    return format_msg(msg, 'giveaway started!  use !giveaway to enter')


@command('!giveaway', secret=True)
async def giveaway(config: Config, msg: Message) -> str:
    async with aiosqlite.connect('db.db') as db:
        await ensure_giveaway_tables_exist(db)

        async with db.execute('SELECT active FROM giveaway') as cursor:
            row = await cursor.fetchone()
            if row is None or not row[0]:
                return format_msg(msg, 'no current giveaway active!')

        await ensure_giveaway_tables_exist(db)
        query = 'INSERT OR REPLACE INTO giveaway_users VALUES (?)'
        await db.execute(query, (msg.display_name,))
        await db.commit()

    return format_msg(msg, f'{esc(msg.display_name)} has been entered!')


@command('!giveawayend', secret=True)
async def giveawayend(config: Config, msg: Message) -> str | None:
    if not msg.is_moderator and msg.name_key != config.channel:
        return None

    async with aiosqlite.connect('db.db') as db:
        await ensure_giveaway_tables_exist(db)

        async with db.execute('SELECT active FROM giveaway') as cursor:
            row = await cursor.fetchone()
            if row is None or not row[0]:
                return format_msg(msg, 'no current giveaway active!')

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
        return format_msg(msg, 'no users entered giveaway!')

    winner = random.choice(users)
    return format_msg(msg, f'!giveaway winner is {esc(winner)}')
