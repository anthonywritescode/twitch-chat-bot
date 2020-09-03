from __future__ import annotations

import argparse
import asyncio.subprocess
import collections
import contextlib
import datetime
import functools
import hashlib
import json
import os.path
import random
import re
import signal
import struct
import sys
import tempfile
import traceback
from typing import Any
from typing import Callable
from typing import Counter
from typing import Dict
from typing import List
from typing import Mapping
from typing import Match
from typing import NamedTuple
from typing import Optional
from typing import Pattern
from typing import Set
from typing import Tuple

import aiohttp
import aiosqlite
import async_lru
import pyjokes
from humanize import naturaldelta

# TODO: allow host / port to be configurable
HOST = 'irc.chat.twitch.tv'
PORT = 6697

MSG_RE = re.compile(
    '^@(?P<info>[^ ]+) :(?P<user>[^!]+).* '
    'PRIVMSG #(?P<channel>[^ ]+) '
    ':(?P<msg>[^\r]+)',
)
PRIVMSG = 'PRIVMSG #{channel} : {msg}\r\n'
SEND_MSG_RE = re.compile('^PRIVMSG #[^ ]+ :(?P<msg>[^\r]+)')
COMMAND_RE = re.compile(r'^(?P<cmd>!\w+)')
COMMAND_PATTERN_RE = re.compile(r'!\w+')
USERNAME_RE = re.compile(r'\w+')


class Config(NamedTuple):
    username: str
    channel: str
    oauth_token: str
    client_id: str

    def __repr__(self) -> str:
        return (
            f'{type(self).__name__}('
            f'username={self.username!r}, '
            f'channel={self.channel!r}, '
            f'oauth_token={"***"!r}, '
            f'client_id={"***"!r}, '
            f')'
        )


def esc(s: str) -> str:
    return s.replace('{', '{{').replace('}', '}}')


def _parse_badge_info(s: str) -> Dict[str, str]:
    ret = {}
    for part in s.split(';'):
        k, v = part.split('=', 1)
        ret[k] = v
    return ret


def _parse_color(s: str) -> Tuple[int, int, int]:
    return int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16)


def _badges(badges: str) -> str:
    ret = ''
    for s, reg in (
        ('\033[48;2;000;000;000m⚙\033[m', re.compile('^staff/')),
        ('\033[48;2;000;173;003m⚔\033[m', re.compile('^moderator/')),
        ('\033[48;2;224;005;185m♦\033[m', re.compile('^vip/')),
        ('\033[48;2;233;025;022m☞\033[m', re.compile('^broadcaster/')),
        ('\033[48;2;130;005;180m★\033[m', re.compile('^founder/')),
        ('\033[48;2;130;005;180m★\033[m', re.compile('^subscriber/')),
        ('\033[48;2;000;160;214m♕\033[m', re.compile('^premium/')),
        ('\033[48;2;089;057;154m♕\033[m', re.compile('^turbo/')),
        ('\033[48;2;230;186;072m◘\033[m', re.compile('^sub-gift-leader/')),
        ('\033[48;2;088;226;193m◘\033[m', re.compile('^sub-gifter/')),
        ('\033[48;2;183;125;029m♕\033[m', re.compile('^hype-train/')),
        ('\033[48;2;203;200;208m▴\033[m', re.compile('^bits/')),
        ('\033[48;2;230;186;072m♦\033[m', re.compile('^bits-leader/')),
        ('\033[48;2;145;070;255m☑\033[m', re.compile('^partner/')),
    ):
        for badge in badges.split(','):
            if reg.match(badge):
                ret += s
    return ret


def _is_moderator(match: Match[str]) -> bool:
    info = _parse_badge_info(match['info'])
    badges = info['badges'].split(',')
    return any(badge.startswith('moderator/') for badge in badges)


def _gen_color(name: str) -> Tuple[int, int, int]:
    h = hashlib.sha256(name.encode())
    n, = struct.unpack('Q', h.digest()[:8])
    bits = [int(s) for s in bin(n)[2:]]

    r = bits[0] * 0b1111111 + (bits[1] << 7)
    g = bits[2] * 0b1111111 + (bits[3] << 7)
    b = bits[4] * 0b1111111 + (bits[5] << 7)
    return r, g, b


def _optional_user_arg(match: Match[str]) -> str:
    _, _, rest = match['msg'].strip().partition(' ')
    if rest:
        return rest.lstrip('@')
    else:
        return match['user']


async def send(
        writer: asyncio.StreamWriter,
        msg: str,
        *,
        quiet: bool = False,
) -> None:
    if not quiet:
        print(f'< {msg}', end='', flush=True, file=sys.stderr)
    writer.write(msg.encode())
    return await writer.drain()


async def recv(
        reader: asyncio.StreamReader,
        *,
        quiet: bool = False,
) -> bytes:
    data = await reader.readline()
    if not quiet:
        sys.stderr.buffer.write(b'> ')
        sys.stderr.buffer.write(data)
        sys.stderr.flush()
    return data


class Response:
    async def __call__(self, config: Config) -> Optional[str]:
        return None


class CmdResponse(Response):
    def __init__(self, cmd: str) -> None:
        self.cmd = cmd

    async def __call__(self, config: Config) -> Optional[str]:
        return self.cmd


class MessageResponse(Response):
    def __init__(self, match: Match[str], msg_fmt: str) -> None:
        self.match = match
        self.msg_fmt = msg_fmt

    async def __call__(self, config: Config) -> Optional[str]:
        params = self.match.groupdict()
        params['msg'] = self.msg_fmt.format(**params)
        return PRIVMSG.format(**params)


Callback = Callable[[Match[str]], Response]
HANDLERS: List[Tuple[Pattern[str], Callback]] = []
COMMANDS: Dict[str, Callback] = {}
POINTS_HANDLERS: Dict[str, Callback] = {}
SECRET_CMDS: Set[str] = set()


def handler(
    *prefixes: str,
    flags: re.RegexFlag = re.U,
) -> Callable[[Callback], Callback]:
    def handler_decorator(func: Callback) -> Callback:
        for prefix in prefixes:
            HANDLERS.append((re.compile(prefix + '\r\n$', flags=flags), func))
        return func
    return handler_decorator


def handle_message(
        *message_prefixes: str,
        flags: re.RegexFlag = re.U,
) -> Callable[[Callback], Callback]:
    return handler(
        *(
            f'^@(?P<info>[^ ]+) :(?P<user>[^!]+).* '
            f'PRIVMSG #(?P<channel>[^ ]+) '
            f':(?P<msg>{message_prefix}.*)'
            for message_prefix in message_prefixes
        ), flags=flags,
    )


def command(
        *cmds: str,
        secret: bool = False,
) -> Callable[[Callback], Callback]:
    def command_decorator(func: Callback) -> Callback:
        for cmd in cmds:
            COMMANDS[cmd] = func
        if secret:
            SECRET_CMDS.update(cmds)
        else:
            SECRET_CMDS.update(cmds[1:])
        return func
    return command_decorator


def channel_points_handler(reward_id: str) -> Callable[[Callback], Callback]:
    def channel_points_handler_decorator(func: Callback) -> Callback:
        POINTS_HANDLERS[reward_id] = func
        return func
    return channel_points_handler_decorator


def add_alias(cmd: str, *aliases: str) -> None:
    for alias in aliases:
        COMMANDS[alias] = COMMANDS[cmd]
        SECRET_CMDS.add(alias)


@handler('^PING (.*)')
def pong(match: Match[str]) -> Response:
    return CmdResponse(f'PONG {match.group(1)}\r\n')


_TEXT_COMMANDS: Tuple[Tuple[str, str], ...] = (
    (
        '!bot',
        'I wrote the bot!  https://github.com/anthonywritescode/twitch-chat-bot',  # noqa: E501
    ),
    (
        '!discord',
        'We do have Discord, you are welcome to join: '
        'https://discord.gg/xDKGPaW',
    ),
    (
        '!distro',
        'awcActuallyWindows Windows 10 with Ubuntu 20.04 LTS virtual machine, '
        'more info here: https://www.youtube.com/watch?v=8KdAqlESQJo',
    ),
    (
        '!donate',
        "donations are appreciated but not necessary -- if you'd like to "
        'donate, you can donate at https://streamlabs.com/anthonywritescode',
    ),
    (
        '!editor',
        'awcBabi this is my text editor I made, called babi! '
        'https://github.com/asottile/babi '
        'more info in this video: https://www.youtube.com/watch?v=WyR1hAGmR3g',
    ),
    (
        '!emotes',
        'awcDumpsterFire awcPythonk awcHelloHello awcKeebL awcKeebR '
        'awcPreCommit awcBabi awcFLogo awcCarpet awcActuallyWindows',
    ),
    (
        '!explain',
        'playlist: https://www.youtube.com/playlist?list=PLWBKAf81pmOaP9naRiNAqug6EBnkPakvY '  # noqa: E501
        'video list: https://github.com/anthonywritescode/explains',
    ),
    (
        '!faq',
        'https://www.youtube.com/playlist?list=PLWBKAf81pmOZEPeIV2_pIESK5hRMAo1hR',  # noqa: E501
    ),
    (
        '!github',
        "anthony's github is https://github.com/asottile -- stream github is "
        'https://github.com/anthonywritescode',
    ),
    ('!homeland', 'WE WILL PROTECT OUR HOMELAND!'),
    (
        '!keyboard',
        'either '
        '(normal) code v3 87-key (cherry mx clears) '
        '(contributed by PhillipWei): https://amzn.to/3jzmwh3 '
        'or '
        '(split) awcKeebL awcKeebR kinesis freestyle pro (cherry mx reds) '
        'https://amzn.to/3jyN4PC (faq: https://youtu.be/DZgCUWf9DZM)',
    ),
    (
        '!keyboard2',
        'this is my second mechanical keyboard: '
        'https://i.fluffy.cc/CDtRzWX1JZTbqzKswHrZsF7HPX2zfLL1.png',
    ),
    (
        '!keyboard3',
        'this is my stream deck keyboard (cherry mx black silent):'
        'https://keeb.io/products/bdn9-3x3-9-key-macropad-rotary-encoder-support '  # noqa: E501
        'here is more info: https://www.youtube.com/watch?v=p2TyRIAxR48',
    ),
    ('!levelup', 'https://i.imgur.com/Uoq5vGx.gif'),
    ('!lurk', 'thanks for lurking, {user}!'),
    ('!ohai', 'ohai, {user}!'),
    ('!playlist', 'HearWeGo: https://www.youtube.com/playlist?list=PL44UysF4ZQ23B_ITIqM8Fqt1UXgsA9yD6'),  # noqa: E501
    (
        '!theme',
        'awcBabi this is vs dark plus in !babi with one modification to '
        'highlight ini headers: '
        'https://github.com/asottile/babi#setting-up-syntax-highlighting',
    ),
    ('!twitter', 'https://twitter.com/codewithanthony'),
    ('!water', 'DRINK WATER, BITCH'),
    ('!youtube', 'https://youtube.com/anthonywritescode'),
)


def _generic_msg_handler(match: Match[str], *, msg: str) -> Response:
    return MessageResponse(match, msg)


for _cmd, _msg in _TEXT_COMMANDS:
    command(_cmd)(functools.partial(_generic_msg_handler, msg=_msg))


@command('!still')
def cmd_still(match: Match[str]) -> Response:
    _, _, rest = match['msg'].partition(' ')
    year = datetime.date.today().year
    lol = random.choice(['LOL', 'LOLW', 'LMAO', 'NUUU'])
    return MessageResponse(match, f'{esc(rest)}, in {year} - {lol}!')


@command('!bonk')
def cmd_bonk(match: Match[str]) -> Response:
    _, _, rest = match['msg'].partition(' ')
    rest = rest.strip() or 'Makayla_Fox'
    return MessageResponse(
        match,
        f'{esc(rest)}: '
        f'https://i.fluffy.cc/DM4QqzjR7wCpkGPwTl6zr907X50XgtBL.png',
    )


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
def cmd_today(match: Match[str]) -> Response:
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
def cmd_settoday(match: Match[str]) -> Response:
    if not _is_moderator(match) and match['user'] != match['channel']:
        return MessageResponse(match, 'https://youtu.be/RfiQYRn7fBg')
    _, _, rest = match['msg'].partition(' ')
    return SetTodayResponse(match, rest)


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


async def get_motd(db: aiosqlite.Connect) -> str:
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
def cmd_set_motd(match: Match[str]) -> Response:
    return SetMotdResponse(match)


class MotdResponse(MessageResponse):
    def __init__(self, match: Match[str]) -> None:
        super().__init__(match, '')

    async def __call__(self, config: Config) -> Optional[str]:
        async with aiosqlite.connect('db.db') as db:
            self.msg_fmt = await get_motd(db)
        return await super().__call__(config)


@command('!motd')
def cmd_motd(match: Match[str]) -> Response:
    return MotdResponse(match)


async def check_call(*cmd: str) -> None:
    proc = await asyncio.subprocess.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    if proc.returncode != 0:
        raise ValueError(cmd, proc.returncode)


class VideoIdeaResponse(MessageResponse):
    def __init__(self, match: Match[str], videoidea: str) -> None:
        super().__init__(
            match,
            'added! https://github.com/asottile/scratch/wiki/anthony-explains-ideas',  # noqa: E501
        )
        self.videoidea = videoidea

    async def __call__(self, config: Config) -> Optional[str]:
        async def _git(*cmd: str) -> None:
            await check_call('git', '-C', tmpdir, *cmd)

        with tempfile.TemporaryDirectory() as tmpdir:
            await _git(
                'clone', '--depth=1', '--quiet',
                'git@github.com:asottile/scratch.wiki', '.',
            )
            ideas_file = os.path.join(tmpdir, 'anthony-explains-ideas.md')
            with open(ideas_file, 'rb+') as f:
                f.seek(-1, os.SEEK_END)
                c = f.read()
                if c != b'\n':
                    f.write(b'\n')
                f.write(f'- {self.videoidea}\n'.encode())
            await _git('add', '.')
            await _git('commit', '-q', '-m', 'idea added by !videoidea')
            await _git('push', '-q', 'origin', 'HEAD')
        return await super().__call__(config)


@command('!wideoidea', '!videoidea')
def cmd_videoidea(match: Match[str]) -> Response:
    if not _is_moderator(match) and match['user'] != match['channel']:
        return MessageResponse(match, 'https://youtu.be/RfiQYRn7fBg')
    _, _, rest = match['msg'].partition(' ')
    return VideoIdeaResponse(match, rest)


def seconds_to_readable(seconds: int) -> str:
    parts = []
    for n, unit in (
            (60 * 60, 'hours'),
            (60, 'minutes'),
            (1, 'seconds'),
    ):
        if seconds // n:
            parts.append(f'{seconds // n} {unit}')
        seconds %= n
    return ', '.join(parts)


class UptimeResponse(Response):
    async def __call__(self, config: Config) -> Optional[str]:
        url = f'https://api.twitch.tv/helix/streams?user_login={config.channel}'  # noqa: E501
        headers = {
            'Authorization': f'Bearer {config.oauth_token.split(":")[1]}',
            'Client-ID': config.client_id,
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                text = await response.text()
                data = json.loads(text)['data']
                if not data:
                    msg = 'not currently streaming!'
                    return PRIVMSG.format(channel=config.channel, msg=msg)
                start_time_s = data[0]['started_at']
                start_time = datetime.datetime.strptime(
                    start_time_s, '%Y-%m-%dT%H:%M:%SZ',
                )
                elapsed = (datetime.datetime.utcnow() - start_time).seconds

                msg = f'streaming for: {seconds_to_readable(elapsed)}'
                return PRIVMSG.format(channel=config.channel, msg=msg)


@command('!uptime')
def cmd_uptime(match: Match[str]) -> Response:
    return UptimeResponse()


@async_lru.alru_cache(maxsize=32)
async def fetch_twitch_user(
        user: str,
        *,
        oauth_token: str,
        client_id: str
) -> Optional[List[Dict[str, Any]]]:
    url = 'https://api.twitch.tv/helix/users'
    params = [('login', user)]
    headers = {
        'Authorization': f'Bearer {oauth_token}',
        'Client-ID': client_id,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            json_resp = await resp.json()
            return json_resp.get('data')


async def fetch_twitch_user_follows(
        *,
        from_id: int,
        to_id: int,
        oauth_token: str,
        client_id: str
) -> Optional[List[Dict[str, Any]]]:
    url = 'https://api.twitch.tv/helix/users/follows'
    params = [('from_id', from_id), ('to_id', to_id)]
    headers = {
        'Authorization': f'Bearer {oauth_token}',
        'Client-ID': client_id,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            json_resp = await resp.json()
            return json_resp.get('data')


class FollowageResponse(Response):
    def __init__(self, username: str) -> None:
        self.username = username

    async def __call__(self, config: Config) -> Optional[str]:
        token = config.oauth_token.split(':')[1]

        fetched_users = await fetch_twitch_user(
            config.channel,
            oauth_token=token,
            client_id=config.client_id,
        )
        assert fetched_users is not None
        me, = fetched_users

        fetched_users = await fetch_twitch_user(
            self.username,
            oauth_token=token,
            client_id=config.client_id,
        )
        if not fetched_users:
            msg = f'user {esc(self.username)} not found!'
            return PRIVMSG.format(channel=config.channel, msg=msg)
        target_user, = fetched_users

        # if streamer wants to check the followage to their own channel
        if me['id'] == target_user['id']:
            msg = (
                f"@{esc(target_user['login'])}, you can't check !followage "
                f'to your own channel.  But I appreciate your curiosity!'
            )
            return PRIVMSG.format(channel=config.channel, msg=msg)

        follow_age_results = await fetch_twitch_user_follows(
            from_id=target_user['id'],
            to_id=me['id'],
            oauth_token=token,
            client_id=config.client_id,
        )
        if not follow_age_results:
            msg = f'{esc(target_user["login"])} is not a follower!'
            return PRIVMSG.format(channel=config.channel, msg=msg)
        follow_age, = follow_age_results

        now = datetime.datetime.utcnow()
        date_of_follow = datetime.datetime.fromisoformat(
            # twitch sends ISO date string with "Z" at the end,
            # which python's fromisoformat method does not like
            follow_age['followed_at'].rstrip('Z'),
        )
        delta = now - date_of_follow
        msg = (
            f'{esc(follow_age["from_name"])} has been following for '
            f'{esc(naturaldelta(delta))}!'
        )
        return PRIVMSG.format(channel=config.channel, msg=msg)


# !followage -> valid, checks the caller
# !followage anthonywritescode -> valid, checks the user passed in payload
# !followage foo bar -> still valid, however the whole
# "foo bar" will be processed as a username
@command('!followage')
def cmd_followage(match: Match[str]) -> Response:
    return FollowageResponse(_optional_user_arg(match))


@handle_message(r'!pep[ ]?(?P<pep_num>\d{1,4})')
def cmd_pep(match: Match[str]) -> Response:
    n = str(int(match['pep_num'])).zfill(4)
    return MessageResponse(match, f'https://www.python.org/dev/peps/pep-{n}/')


@command('!joke')
def cmd_joke(match: Match[str]) -> Response:
    return MessageResponse(match, esc(pyjokes.get_joke()))


@command('!so', secret=True)
def cmd_shoutout(match: Match[str]) -> Response:
    channel = _optional_user_arg(match)
    user_match = USERNAME_RE.match(channel)
    if not _is_moderator(match) and match['user'] != match['channel']:
        return MessageResponse(match, 'https://youtu.be/RfiQYRn7fBg')
    elif channel == match['user'] or user_match is None:
        return Response()
    user = user_match[0]
    return MessageResponse(
        match,
        f'you should check out https://twitch.tv/{esc(user)} !',
    )


_ALIASES = (
    ('!editor', ('!babi', '!nano', '!vim', '!emacs', '!vscode')),
    ('!emotes', ('!emoji', '!emote')),
    ('!explain', ('!explains',)),
    ('!distro', ('!os',)),
)
for _alias_name, _aliases in _ALIASES:
    add_alias(_alias_name, *_aliases)


CHAT_LOG_RE = re.compile(
    r'^\[[^]]+\][^<*]*(<(?P<chat_user>[^>]+)>|\* (?P<action_user>[^ ]+))',
)
BONKER_RE = re.compile(r'^\[[^]]+\][^<*]*<(?P<chat_user>[^>]+)> !bonk\b')
BONKED_RE = re.compile(r'^\[[^]]+\][^<*]*<[^>]+> !bonk @?(?P<chat_user>\w+)')


@functools.lru_cache(maxsize=None)
def _counts_per_file(filename: str, reg: Pattern[str]) -> Mapping[str, int]:
    counts: Counter[str] = collections.Counter()
    with open(filename) as f:
        for line in f:
            match = reg.match(line)
            if match is None:
                assert reg is not CHAT_LOG_RE
                continue
            user = match['chat_user'] or match['action_user']
            assert user, line
            counts[user.lower()] += 1
    return counts


def _chat_rank_counts(reg: Pattern[str]) -> Counter[str]:
    total: Counter[str] = collections.Counter()
    for filename in os.listdir('logs'):
        full_filename = os.path.join('logs', filename)
        if filename != f'{datetime.date.today()}.log':
            total.update(_counts_per_file(full_filename, reg))
        else:
            # don't use the cached version for today's logs
            total.update(_counts_per_file.__wrapped__(full_filename, reg))
    return total


def _rank(username: str, reg: Pattern[str]) -> Optional[Tuple[int, int]]:
    total = _chat_rank_counts(reg)

    username = username.lower()
    for i, (candidate, count) in enumerate(total.most_common(), start=1):
        if candidate == username:
            return i, count
    else:
        return None


@functools.lru_cache(maxsize=1)
def _log_start_date() -> str:
    logs_start = min(os.listdir('logs'))
    logs_start, _, _ = logs_start.partition('.')
    return logs_start


@command('!chatrank')
def cmd_chatrank(match: Match[str]) -> Response:
    user = _optional_user_arg(match)
    ret = _rank(user, CHAT_LOG_RE)
    if ret is None:
        return MessageResponse(match, f'user not found {esc(user)}')
    else:
        rank, n = ret
        return MessageResponse(
            match,
            f'{esc(user)} is ranked #{rank} with {n} messages '
            f'(since {_log_start_date()})',
        )


@command('!top10chat')
def cmd_top_10_chat(match: Match[str]) -> Response:
    total = _chat_rank_counts(CHAT_LOG_RE)
    user_list = ', '.join(
        f'{rank}. {user}({n})'
        for rank, (user, n) in enumerate(total.most_common(10), start=1)
    )
    return MessageResponse(match, f'{user_list} (since {_log_start_date()})')


@command('!bonkrank')
def cmd_bonkrank(match: Match[str]) -> Response:
    user = _optional_user_arg(match)
    ret = _rank(user, BONKER_RE)
    if ret is None:
        return MessageResponse(match, f'user not found {esc(user)}')
    else:
        rank, n = ret
        return MessageResponse(
            match,
            f'{esc(user)} is ranked #{rank}, has bonked others {n} times',
        )


@command('!top5bonkers')
def cmd_top_5_bonkers(match: Match[str]) -> Response:
    total = _chat_rank_counts(BONKER_RE)
    user_list = ', '.join(
        f'{rank}. {user}({n})'
        for rank, (user, n) in enumerate(total.most_common(5), start=1)
    )
    return MessageResponse(match, user_list)


@command('!bonkedrank')
def cmd_bonkedrank(match: Match[str]) -> Response:
    user = _optional_user_arg(match)
    ret = _rank(user, BONKED_RE)
    if ret is None:
        return MessageResponse(match, f'user not found {esc(user)}')
    else:
        rank, n = ret
        return MessageResponse(
            match,
            f'{esc(user)} is ranked #{rank}, has been bonked {n} times',
        )


@command('!top5bonked')
def cmd_top_5_bonked(match: Match[str]) -> Response:
    total = _chat_rank_counts(BONKED_RE)
    user_list = ', '.join(
        f'{rank}. {user}({n})'
        for rank, (user, n) in enumerate(total.most_common(5), start=1)
    )
    return MessageResponse(match, user_list)


@handle_message(r'!\w')
def cmd_help(match: Match[str]) -> Response:
    possible = [COMMAND_PATTERN_RE.search(reg.pattern) for reg, _ in HANDLERS]
    possible_cmds = {match[0] for match in possible if match}
    possible_cmds.update(COMMANDS)
    possible_cmds.difference_update(SECRET_CMDS)
    commands = ['!help'] + sorted(possible_cmds)
    msg = f'possible commands: {", ".join(commands)}'
    if not match['msg'].startswith('!help'):
        msg = f'unknown command ({esc(match["msg"].split()[0])}), {msg}'
    return MessageResponse(match, msg)


@handle_message('PING')
def msg_ping(match: Match[str]) -> Response:
    _, _, rest = match['msg'].partition(' ')
    return MessageResponse(match, f'PONG {esc(rest)}')


@handle_message(
    r'.*\b(?P<word>nano|linux|windows|emacs|NT)\b', flags=re.IGNORECASE,
)
def msg_gnu_please(match: Match[str]) -> Response:
    if random.randrange(0, 100) < 90:
        return Response()
    msg, word = match['msg'], match['word']
    query = re.search(f'gnu[/+]{word}', msg, flags=re.IGNORECASE)
    if query:
        return MessageResponse(match, f'YES! {query[0]}')
    else:
        return MessageResponse(match, f"Um please, it's GNU+{esc(word)}!")


@handle_message('(is this|are you using) (vim|nano)', flags=re.IGNORECASE)
def msg_is_this_vim(match: Match[str]) -> Response:
    return COMMANDS['!editor'](match)


@handle_message(r'.*\bth[oi]nk(?:ing)?\b', flags=re.IGNORECASE)
def msg_think(match: Match[str]) -> Response:
    return MessageResponse(match, 'awcPythonk ' * 5)


# TODO: !tags, only allowed by stream admin / mods????

def dt_str() -> str:
    dt_now = datetime.datetime.now()
    return f'[{dt_now.hour:02}:{dt_now.minute:02}]'


def _shutdown(
        writer: asyncio.StreamWriter,
        loop: asyncio.AbstractEventLoop,
        shutdown_task: Optional[asyncio.Task[Any]] = None,
) -> None:
    print('bye!')
    ignored_tasks = set()
    if shutdown_task is not None:
        ignored_tasks.add(shutdown_task)

    if writer:
        writer.close()
        closing_task = loop.create_task(writer.wait_closed())

        def cancel_tasks(fut: asyncio.Future[Any]) -> None:
            tasks = [t for t in asyncio.all_tasks() if t not in ignored_tasks]
            for task in tasks:
                task.cancel()

        closing_task.add_done_callback(cancel_tasks)


UNCOLOR_RE = re.compile(r'\033\[[^m]*m')


class LogWriter:
    def __init__(self) -> None:
        self.date = str(datetime.date.today())

    def write_message(self, msg: str) -> None:
        print(msg)
        uncolored_msg = UNCOLOR_RE.sub('', msg)
        os.makedirs('logs', exist_ok=True)
        log = os.path.join('logs', f'{self.date}.log')
        with open(log, 'a+', encoding='UTF-8') as f:
            f.write(f'{uncolored_msg}\n')


async def handle_response(
        config: Config,
        match: Match[str],
        handler: Callable[[Match[str]], Response],
        writer: asyncio.StreamWriter,
        log_writer: LogWriter,
        *,
        quiet: bool,
) -> None:
    try:
        res = await handler(match)(config)
    except Exception as e:
        traceback.print_exc()
        res = PRIVMSG.format(
            channel=config.channel,
            msg=f'*** unhandled {type(e).__name__} -- see logs',
        )
    if res is not None:
        send_match = SEND_MSG_RE.match(res)
        if send_match:
            color = '\033[1m\033[3m\033[38;5;21m'
            log_writer.write_message(
                f'{dt_str()}'
                f'<{color}{config.username}\033[m> '
                f'{send_match[1]}',
            )
        await send(writer, res, quiet=quiet)


async def amain(config: Config, *, quiet: bool) -> None:
    log_writer = LogWriter()
    reader, writer = await asyncio.open_connection(HOST, PORT, ssl=True)

    loop = asyncio.get_event_loop()
    shutdown_cb = functools.partial(_shutdown, writer, loop)
    try:
        loop.add_signal_handler(signal.SIGINT, shutdown_cb)
    except NotImplementedError:
        # Doh... Windows...
        signal.signal(signal.SIGINT, lambda *_: shutdown_cb())

    await send(writer, f'PASS {config.oauth_token}\r\n', quiet=True)
    await send(writer, f'NICK {config.username}\r\n', quiet=quiet)
    await send(writer, f'JOIN #{config.channel}\r\n', quiet=quiet)
    await send(writer, 'CAP REQ :twitch.tv/tags\r\n', quiet=quiet)

    while not writer.is_closing():
        data = await recv(reader, quiet=quiet)
        if not data:
            return
        msg = data.decode('UTF-8', errors='backslashreplace')

        msg_match = MSG_RE.match(msg)
        if msg_match:
            info = _parse_badge_info(msg_match['info'])
            if info['color']:
                r, g, b = _parse_color(info['color'])
            else:
                r, g, b = _gen_color(info['display-name'])

            color_start = f'\033[1m\033[38;2;{r};{g};{b}m'

            if msg_match['msg'].startswith('\x01ACTION '):
                log_writer.write_message(
                    f'{dt_str()}'
                    f'{_badges(info["badges"])}'
                    f'{color_start}\033[3m * {info["display-name"]}\033[22m '
                    f'{msg_match["msg"][8:-1]}\033[m',
                )
            else:
                if info.get('msg-id') == 'highlighted-message':
                    msg_s = f'\033[48;2;117;094;188m{msg_match["msg"]}\033[m'
                elif 'custom-reward-id' in info:
                    msg_s = f'\033[48;2;029;091;130m{msg_match["msg"]}\033[m'
                else:
                    msg_s = msg_match['msg']

                log_writer.write_message(
                    f'{dt_str()}'
                    f'{_badges(info["badges"])}'
                    f'<{color_start}{info["display-name"]}\033[m> '
                    f'{msg_s}',
                )

            if 'custom-reward-id' in info:
                if info['custom-reward-id'] in POINTS_HANDLERS:
                    handler = POINTS_HANDLERS[info['custom-reward-id']]
                    coro = handle_response(
                        config, msg_match, handler, writer, log_writer,
                        quiet=quiet,
                    )
                    loop.create_task(coro)
                elif not quiet:
                    print(f'UNHANDLED reward({info["custom-reward-id"]})')
                continue

        if msg_match:
            cmd_match = COMMAND_RE.match(msg_match['msg'])
            if cmd_match and cmd_match['cmd'].lower() in COMMANDS:
                handler = COMMANDS[cmd_match['cmd'].lower()]
                coro = handle_response(
                    config, msg_match, handler, writer, log_writer,
                    quiet=quiet,
                )
                loop.create_task(coro)
                continue

        for pattern, handler in HANDLERS:
            match = pattern.match(msg)
            if match:
                coro = handle_response(
                    config, match, handler, writer, log_writer, quiet=quiet,
                )
                loop.create_task(coro)
                break
        else:
            if not quiet:
                print(f'UNHANDLED: {msg}', end='')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    with open(args.config) as f:
        config = Config(**json.load(f))

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(amain(config, quiet=not args.verbose))

    return 0


if __name__ == '__main__':
    exit(main())
