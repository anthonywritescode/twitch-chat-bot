from typing import Match
from typing import Optional

import aiosqlite

from bot.config import Config
from bot.data import channel_points_handler
from bot.data import command
from bot.data import esc
from bot.data import MessageResponse


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


class SetMotdResponse(MessageResponse):
    def __init__(self, match: Match[str]) -> None:
        super().__init__(match, 'motd updated!  thanks for spending points!')
        self.user = match['user']
        self.msg = match['msg']

    async def __call__(self, config: Config) -> Optional[str]:
        async with aiosqlite.connect('db.db') as db:
            await set_motd(db, self.user, self.msg)
        return await super().__call__(config)


@channel_points_handler('a2fa47a2-851e-40db-b909-df001801cade')
def cmd_set_motd(match: Match[str]) -> SetMotdResponse:
    return SetMotdResponse(match)


class MotdResponse(MessageResponse):
    def __init__(self, match: Match[str]) -> None:
        super().__init__(match, '')

    async def __call__(self, config: Config) -> Optional[str]:
        async with aiosqlite.connect('db.db') as db:
            self.msg_fmt = await get_motd(db)
        return await super().__call__(config)


@command('!motd')
def cmd_motd(match: Match[str]) -> MotdResponse:
    return MotdResponse(match)
