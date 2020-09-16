from typing import Match
from typing import Optional

import aiosqlite

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import MessageResponse
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


class TodayResponse(MessageResponse):
    def __init__(self, match: Match[str]) -> None:
        super().__init__(match, '')

    async def __call__(self, config: Config) -> Optional[str]:
        async with aiosqlite.connect('db.db') as db:
            self.msg_fmt = await get_today(db)
        return await super().__call__(config)


@command('!today', '!project')
def cmd_today(match: Match[str]) -> TodayResponse:
    return TodayResponse(match)


class SetTodayResponse(MessageResponse):
    def __init__(self, match: Match[str], msg: str) -> None:
        super().__init__(match, 'updated!')
        self.msg = msg

    async def __call__(self, config: Config) -> Optional[str]:
        async with aiosqlite.connect('db.db') as db:
            await set_today(db, self.msg)
        return await super().__call__(config)


@command('!settoday', secret=True)
def cmd_settoday(match: Match[str]) -> MessageResponse:
    if not is_moderator(match) and match['user'] != match['channel']:
        return MessageResponse(match, 'https://youtu.be/RfiQYRn7fBg')
    _, _, rest = match['msg'].partition(' ')
    return SetTodayResponse(match, rest)
