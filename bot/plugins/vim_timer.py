from __future__ import annotations

import collections
import datetime
import os.path
from collections import Counter

import aiosqlite

from bot.config import Config
from bot.data import bits_handler
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.data import periodic_handler
from bot.message import Message
from bot.ranking import tied_rank
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
async def vim_bits_handler(config: Config, msg: Message) -> str:
    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)
        enabled = await get_enabled(db)

        bits = int(msg.info['bits'])
        if enabled:
            # TODO: fix casing of names
            time_left = await add_bits(db, msg.name_key, bits)
        else:
            time_left = await add_bits_off(db, msg.name_key, bits)

    if enabled:
        await _set_symlink(should_be_vim=True)

        return format_msg(
            msg,
            f'MOAR VIM: {seconds_to_readable(time_left)} remaining',
        )
    else:
        return format_msg(
            msg,
            f'vim is currently disabled '
            f'{seconds_to_readable(time_left)} banked',
        )


async def _get_user_vim_bits(
    db: aiosqlite.Connection,
) -> Counter[str]:
    vim_bits_query = 'SELECT user, SUM(bits) FROM vim_bits GROUP BY user'
    async with db.execute(vim_bits_query) as cursor:
        rows = await cursor.fetchall()
        bits_counts = collections.Counter(dict(rows))
        return bits_counts


async def _user_rank_by_bits(
        username: str, db: aiosqlite.Connection,
) -> tuple[int, int] | None:
    total = await _get_user_vim_bits(db)
    target_username = username.lower()
    for rank, (count, users) in tied_rank(total.most_common()):
        for username, _ in users:
            if target_username == username.lower():
                return rank, count
    else:
        return None


async def _top_n_rank_by_bits(
    db: aiosqlite.Connection, n: int = 5,
) -> list[str]:
    total = await _get_user_vim_bits(db)
    user_list = []
    for rank, (count, users) in tied_rank(total.most_common(n)):
        usernames = ', '.join(username for username, _ in users)
        user_list.append(f'{rank}. {usernames} ({count})')
    return user_list


@command('!top5vimbits', '!topvimbits', secret=True)
async def cmd_topvimbits(config: Config, msg: Message) -> str:
    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)
        top_10_s = ', '.join(await _top_n_rank_by_bits(db, n=5))
        return format_msg(msg, f'{top_10_s}')


@command('!vimbitsrank', secret=True)
async def cmd_vimbitsrank(config: Config, msg: Message) -> str:
    # TODO: handle display name properly
    user = msg.optional_user_arg.lower()
    async with aiosqlite.connect('db.db') as db:
        ret = await _user_rank_by_bits(user, db)
        if ret is None:
            return format_msg(msg, f'user not found {esc(user)}')
        else:
            rank, n = ret
            return format_msg(
                msg,
                f'{esc(user)} is ranked #{rank} with {n} vim bits',
            )


@command('!vimtimeleft', secret=True)
async def cmd_vimtimeleft(config: Config, msg: Message) -> str:
    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)
        if not await get_enabled(db):
            return format_msg(msg, 'vim is currently disabled')

        time_left = await get_time_left(db)
        if time_left == 0:
            return format_msg(msg, 'not currently using vim')
        else:
            return format_msg(
                msg,
                f'vim time remaining: {seconds_to_readable(time_left)}',
            )


@command('!disablevim', secret=True)
async def cmd_disablevim(config: Config, msg: Message) -> str:
    if not msg.is_moderator and msg.name_key != config.channel:
        return format_msg(msg, 'https://youtu.be/RfiQYRn7fBg')

    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)

        await db.execute('INSERT INTO vim_enabled VALUES (0)')
        await db.commit()

    return format_msg(msg, 'vim has been disabled')


@command('!enablevim', secret=True)
async def cmd_enablevim(config: Config, msg: Message) -> str:
    if not msg.is_moderator and msg.name_key != config.channel:
        return format_msg(msg, 'https://youtu.be/RfiQYRn7fBg')

    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)

        await db.execute('INSERT INTO vim_enabled VALUES (1)')
        move_query = 'INSERT INTO vim_bits SELECT * FROM vim_bits_disabled'
        await db.execute(move_query)
        time_left = await add_time(db, await disabled_seconds(db))
        await db.execute('DELETE FROM vim_bits_disabled')
        await db.commit()

    if time_left == 0:
        return format_msg(msg, 'vim has been enabled')
    else:
        await _set_symlink(should_be_vim=True)
        return format_msg(
            msg,
            f'vim has been enabled: '
            f'time remaining {seconds_to_readable(time_left)}',
        )


@command(
    '!editor',
    '!babi', '!nano', '!vim', '!emacs', '!vscode', '!wheredobabiscomefrom',
)
async def cmd_editor(config: Config, msg: Message) -> str:
    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)
        if await get_time_left(db):
            return format_msg(
                msg,
                'I am currently being forced to use vim by viewers. '
                'awcBabi I normally use my text editor I made, called babi! '
                'https://github.com/asottile/babi more info in this video: '
                'https://www.youtube.com/watch?v=WyR1hAGmR3g',
            )
        else:
            return format_msg(
                msg,
                'awcBabi this is my text editor I made, called babi! '
                'https://github.com/asottile/babi more info in this video: '
                'https://www.youtube.com/watch?v=WyR1hAGmR3g',
            )


@periodic_handler(seconds=5)
async def vim_normalize_state(config: Config, msg: Message) -> str | None:
    async with aiosqlite.connect('db.db') as db:
        await ensure_vim_tables_exist(db)
        time_left = await get_time_left(db)

    cleared_vim = await _set_symlink(should_be_vim=time_left > 0)
    if cleared_vim:
        return format_msg(msg, 'vim no more! you are free!')
    else:
        return None
