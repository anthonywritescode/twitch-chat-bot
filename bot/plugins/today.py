from __future__ import annotations

from typing import Match

import aiosqlite

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.permissions import is_moderator


async def ensure_today_table_exists(db: aiosqlite.Connection) -> None:
    await db.execute(
        'CREATE TABLE IF NOT EXISTS today ('
        '   msg TEXT NOT NULL,'
        '   timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        ')',
    )
    await db.commit()


async def set_today(db: aiosqlite.Connection, msg: str) -> None:
    await ensure_today_table_exists(db)
    await db.execute('INSERT INTO today (msg) VALUES (?)', (msg,))
    await db.commit()


async def get_today(db: aiosqlite.Connection) -> str:
    await ensure_today_table_exists(db)
    query = 'SELECT msg FROM today ORDER BY ROWID DESC LIMIT 1'
    async with db.execute(query) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return 'not working on anything?'
        else:
            return esc(row[0])


@command('!today', '!project')
async def cmd_today(config: Config, match: Match[str]) -> str:
    async with aiosqlite.connect('db.db') as db:
        return format_msg(match, await get_today(db))


@command('!settoday', secret=True)
async def cmd_settoday(config: Config, match: Match[str]) -> str:
    if not is_moderator(match) and match['user'] != match['channel']:
        return format_msg(match, 'https://youtu.be/RfiQYRn7fBg')
    _, _, rest = match['msg'].partition(' ')

    async with aiosqlite.connect('db.db') as db:
        await set_today(db, rest)

    return format_msg(match, 'updated!')
