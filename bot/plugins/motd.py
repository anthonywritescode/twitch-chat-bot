from __future__ import annotations

from typing import Match

import aiosqlite

from bot.config import Config
from bot.data import channel_points_handler
from bot.data import command
from bot.data import esc
from bot.data import format_msg


async def ensure_motd_table_exists(db: aiosqlite.Connection) -> None:
    await db.execute(
        'CREATE TABLE IF NOT EXISTS motd ('
        '   user TEXT NOT NULL,'
        '   msg TEXT NOT NULL,'
        '   points INT NOT NULL,'
        '   timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        ')',
    )
    await db.commit()


async def set_motd(db: aiosqlite.Connection, user: str, msg: str) -> None:
    await ensure_motd_table_exists(db)
    query = 'INSERT INTO motd (user, msg, points) VALUES (?, ?, ?)'
    await db.execute(query, (user, msg, 250))
    await db.commit()


async def get_motd(db: aiosqlite.Connection) -> str:
    await ensure_motd_table_exists(db)
    query = 'SELECT msg FROM motd ORDER BY ROWID DESC LIMIT 1'
    async with db.execute(query) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return 'nothing???'
        else:
            return esc(row[0])


async def msg_count(db: aiosqlite.Connection, msg: str) -> int:
    await ensure_motd_table_exists(db)
    query = 'SELECT COUNT(1) FROM motd WHERE msg = ?'
    async with db.execute(query, (msg,)) as cursor:
        ret, = await cursor.fetchone()
        return ret


@channel_points_handler('a2fa47a2-851e-40db-b909-df001801cade')
async def cmd_set_motd(config: Config, match: Match[str]) -> str:
    async with aiosqlite.connect('db.db') as db:
        await set_motd(db, match['user'], match['msg'])
        msg = 'motd updated!  thanks for spending points!'
        if match['msg'] == '!motd':
            motd_count = await msg_count(db, match['msg'])
            msg = f'{msg}  it has been set to !motd {motd_count} times!'
    return format_msg(match, msg)


@command('!motd')
async def cmd_motd(config: Config, match: Match[str]) -> str:
    async with aiosqlite.connect('db.db') as db:
        return format_msg(match, await get_motd(db))
