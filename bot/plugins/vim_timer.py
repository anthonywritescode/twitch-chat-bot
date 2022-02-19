from __future__ import annotations

import datetime
import os.path
from typing import Match

import aiosqlite

from bot.config import Config
from bot.data import bits_handler
from bot.data import command
from bot.data import format_msg
from bot.data import periodic_handler
from bot.permissions import is_moderator
from bot.permissions import parse_badge_info
from bot.util import check_call
from bot.util import seconds_to_readable

# periodic: per-second check to restore state
# data:
# - (datetime, user, bits)
# - (end datetime)
# - (enabled)
# commands:
# - bits handler
# - !vimtimeleft
# - !vimdisable
# - !vimenable

_VIM_BITS_TABLE = '''\
CREATE TABLE IF NOT EXISTS vim_bits (
    user TEXT NOT NULL,
    bits INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
'''
_VIM_BITS_DISABLED_TABLE = '''\
CREATE TABLE IF NOT EXISTS vim_bits_disabled (
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
_VIM_ENABLED_TABLE = '''\
CREATE TABLE IF NOT EXISTS vim_enabled (
    enabled INT NOT NULL
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
    await db.execute(_VIM_BITS_DISABLED_TABLE)
    await db.execute(_VIM_TIME_LEFT_TABLE)
    await db.execute(_VIM_ENABLED_TABLE)
    await db.commit()


async def get_enabled(db: aiosqlite.Connection) -> bool:
    query = 'SELECT enabled FROM vim_enabled ORDER BY ROWID DESC LIMIT 1'
    async with db.execute(query) as cursor:
        ret = await cursor.fetchone()
        if ret is None:
            return True
        else:
            enabled, = ret
            return bool(enabled)


async def get_time_left(db: aiosqlite.Connection) -> int:
    if not await get_enabled(db):
        return 0

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


def _bits_to_seconds(bits: int) -> int:
    return 60 * (100 + bits - 51) // 100


async def add_time(db: aiosqlite.Connection, seconds: int) -> int:
    time_left = await get_time_left(db)
    time_left += seconds
    await db.execute(
        'INSERT INTO vim_time_left VALUES (?)',
        (datetime.datetime.now() + datetime.timedelta(seconds=time_left),),
    )
    return time_left


async def add_bits(db: aiosqlite.Connection, user: str, bits: int) -> int:
    vim_bits_query = 'INSERT INTO vim_bits (user, bits) VALUES (?, ?)'
    await db.execute(vim_bits_query, (user, bits))
    time_left = await add_time(db, _bits_to_seconds(bits))
    await db.commit()
    return time_left


async def disabled_seconds(db: aiosqlite.Connection) -> int:
    async with db.execute('SELECT bits FROM vim_bits_disabled') as cursor:
        rows = await cursor.fetchall()
        return sum(_bits_to_seconds(bits) for bits, in rows)


async def add_bits_off(db: aiosqlite.Connection, user: str, bits: int) -> int:
    vim_bits_query = 'INSERT INTO vim_bits_disabled (user, bits) VALUES (?, ?)'
    await db.execute(vim_bits_query, (user, bits))
    time_left = await disabled_seconds(db)
    await db.commit()
    return time_left


@bits_handler(51)
async def vim_bits_handler(config: Config, match: Match[str]) -> str:
    info = parse_badge_info(match['info'])

    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)
        enabled = await get_enabled(db)

        bits = int(info['bits'])
        if enabled:
            time_left = await add_bits(db, match['user'], bits)
        else:
            time_left = await add_bits_off(db, match['user'], bits)

    if enabled:
        await _set_symlink(should_be_vim=True)

        return format_msg(
            match,
            f'MOAR VIM: {seconds_to_readable(time_left)} remaining',
        )
    else:
        return format_msg(
            match,
            f'vim is currently disabled '
            f'{seconds_to_readable(time_left)} banked',
        )


@command('!vimtimeleft', secret=True)
async def cmd_vimtimeleft(config: Config, match: Match[str]) -> str:
    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)
        if not await get_enabled(db):
            return format_msg(match, 'vim is currently disabled')

        time_left = await get_time_left(db)
        if time_left == 0:
            return format_msg(match, 'not currently using vim')
        else:
            return format_msg(
                match,
                f'vim time remaining: {seconds_to_readable(time_left)}',
            )


@command('!disablevim', secret=True)
async def cmd_disablevim(config: Config, match: Match[str]) -> str:
    if not is_moderator(match) and match['user'] != match['channel']:
        return format_msg(match, 'https://youtu.be/RfiQYRn7fBg')

    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)

        await db.execute('INSERT INTO vim_enabled VALUES (0)')
        await db.commit()

    return format_msg(match, 'vim has been disabled')


@command('!enablevim', secret=True)
async def cmd_enablevim(config: Config, match: Match[str]) -> str:
    if not is_moderator(match) and match['user'] != match['channel']:
        return format_msg(match, 'https://youtu.be/RfiQYRn7fBg')

    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)

        await db.execute('INSERT INTO vim_enabled VALUES (1)')
        move_query = 'INSERT INTO vim_bits SELECT * FROM vim_bits_disabled'
        await db.execute(move_query)
        time_left = await add_time(db, await disabled_seconds(db))
        await db.execute('DELETE FROM vim_bits_disabled')
        await db.commit()

    if time_left == 0:
        return format_msg(match, 'vim has been enabled')
    else:
        await _set_symlink(should_be_vim=True)
        return format_msg(
            match,
            f'vim has been enabled: '
            f'time remaining {seconds_to_readable(time_left)}',
        )


@command('!editor')
async def cmd_editor(config: Config, match: Match[str]) -> str:
    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)
        if await get_enabled(db):
            return format_msg(
                match,
                'I am currently being forced to use vim by viewers. '
                'awcBabi I normally use my text editor I made, called babi! '
                'https://github.com/asottile/babi more info in this video: '
                'https://www.youtube.com/watch?v=WyR1hAGmR3g',
            )
        else:
            return format_msg(
                match,
                'awcBabi this is my text editor I made, called babi! '
                'https://github.com/asottile/babi more info in this video: '
                'https://www.youtube.com/watch?v=WyR1hAGmR3g',
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
