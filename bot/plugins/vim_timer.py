from __future__ import annotations

import datetime
import os.path
from typing import Match

import aiosqlite

from bot.config import Config
from bot.data import command
from bot.data import format_msg
from bot.data import handler
from bot.data import MSG_RE
from bot.data import periodic_handler
from bot.util import check_call
from bot.util import seconds_to_readable

# periodic: per-second check to restore state
# data:
# - (datetime, user, bits)
# - (end datetime)
# commands:
# - bits handler
# - !vimtimeleft

_VIM_BITS_TABLE = '''\
CREATE TABLE IF NOT EXISTS vim_bits (
    user TEXT NOT NULL,
    bits INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
'''
_VIM_TIME_LEFT_TABLE = '''\
CREATE TABLE IF NOT EXISTS vim_time_left (
    timestamp TIMESTAMP NOT NULL
)
'''


async def _ln_sf(dest: str, link: str) -> None:
    await check_call('ln', '-sf', dest, link)


async def _set_symlink(*, should_be_vim: bool) -> bool:
    babi_path = os.path.expanduser('~/opt/venv/bin/babi')
    vim_path = os.path.expanduser('/usr/bin/vim')
    babi_bin = os.path.expanduser('~/bin/babi')

    path = os.path.realpath(babi_bin)

    if should_be_vim and path != vim_path:
        await _ln_sf(dest=vim_path, link=babi_bin)
        return False
    elif not should_be_vim and path != babi_path:
        await _ln_sf(dest=babi_path, link=babi_bin)
        return True
    else:
        return False


async def ensure_vim_tables_exist(db: aiosqlite.Connection) -> None:
    await db.execute(_VIM_BITS_TABLE)
    await db.execute(_VIM_TIME_LEFT_TABLE)
    await db.commit()


async def get_time_left(db: aiosqlite.Connection) -> int:
    query = 'SELECT timestamp FROM vim_time_left ORDER BY ROWID DESC LIMIT 1'
    async with db.execute(query) as cursor:
        ret = await cursor.fetchone()
        if ret is None:
            return 0
        else:
            dt = datetime.datetime.fromisoformat(ret[0])
            if dt < datetime.datetime.now():
                return 0
            else:
                return (dt - datetime.datetime.now()).seconds


async def add_bits(db: aiosqlite.Connection, user: str, bits: int) -> int:
    vim_bits_query = 'INSERT INTO vim_bits (user, bits) VALUES (?, ?)'
    await db.execute(vim_bits_query, (user, bits))
    time_left = await get_time_left(db)
    time_left += 60 * (100 + bits - 51) // 100
    await db.execute(
        'INSERT INTO vim_time_left VALUES (?)',
        (datetime.datetime.now() + datetime.timedelta(seconds=time_left),),
    )
    await db.commit()
    return time_left


@handler(fr'(?=[^ ]+;bits=(?P<bits>\d*51);){MSG_RE.pattern}')
async def vim_bits_handler(config: Config, match: Match[str]) -> str:
    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)
        time_left = await add_bits(db, match['user'], int(match['bits']))

    await _set_symlink(should_be_vim=True)

    return format_msg(
        match,
        f'MOAR VIM: {seconds_to_readable(time_left)} remaining',
    )


@command('!vimtimeleft', secret=True)
async def cmd_vimtimeleft(config: Config, match: Match[str]) -> str:
    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)
        time_left = await get_time_left(db)
        if time_left == 0:
            return format_msg(match, 'not currently using vim')
        else:
            return format_msg(
                match,
                f'vim time remaining: {seconds_to_readable(time_left)}',
            )


@periodic_handler(seconds=5)
async def vim_normalize_state(config: Config, match: Match[str]) -> str | None:
    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)
        time_left = await get_time_left(db)

    cleared_vim = await _set_symlink(should_be_vim=time_left > 0)
    if cleared_vim:
        return format_msg(match, 'vim no more! you are free!')
    else:
        return None
