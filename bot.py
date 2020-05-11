import argparse
import asyncio.subprocess
import datetime
import functools
import hashlib
import json
import os.path
import random
import re
import struct
import sys
import tempfile
import traceback
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Match
from typing import NamedTuple
from typing import NoReturn
from typing import Optional
from typing import Pattern
from typing import Tuple

import aiohttp
import aiosqlite
import async_lru
import pyjokes
from humanize import naturaldelta

# TODO: allow host / port to be configurable
HOST = 'irc.chat.twitch.tv'
PORT = 6697

MSG_RE = re.compile('^@([^ ]+) :([^!]+).* PRIVMSG #[^ ]+ :([^\r]+)')
PRIVMSG = 'PRIVMSG #{channel} : {msg}\r\n'
SEND_MSG_RE = re.compile('^PRIVMSG #[^ ]+ :(?P<msg>[^\r]+)')


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
        ('\033[48;2;224;005;185m♦\033[m', re.compile('^vip/')),
        ('\033[48;2;233;025;022m☞\033[m', re.compile('^broadcaster/')),
        ('\033[48;2;130;005;180m★\033[m', re.compile('^founder/')),
        ('\033[48;2;130;005;180m★\033[m', re.compile('^subscriber/')),
        ('\033[48;2;000;160;214m♕\033[m', re.compile('^premium/')),
        ('\033[48;2;088;226;193m◘\033[m', re.compile('^sub-gifter/')),
        ('\033[48;2;203;200;208m▴\033[m', re.compile('^bits/')),
        ('\033[48;2;230;186;072m♦\033[m', re.compile('^bits-leader/')),
    ):
        for badge in badges.split(','):
            if reg.match(badge):
                ret += s
    return ret


def _gen_color(name: str) -> Tuple[int, int, int]:
    h = hashlib.sha256(name.encode())
    n, = struct.unpack('Q', h.digest()[:8])
    bits = [int(s) for s in bin(n)[2:]]

    r = bits[0] * 0b1111111 + (bits[1] << 7)
    g = bits[2] * 0b1111111 + (bits[3] << 7)
    b = bits[4] * 0b1111111 + (bits[5] << 7)
    return r, g, b


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
    if not data:
        raise SystemExit('unexpected EOF')
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
HANDLERS: List[Tuple[Pattern[str], Callable[[Match[str]], Response]]]
HANDLERS = []


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


@handler('^PING (.*)')
def pong(match: Match[str]) -> Response:
    return CmdResponse(f'PONG {match.group(1)}\r\n')


_TEXT_COMMANDS = (
    # this one has to be first so it does not get overridden by !keyboard
    (
        '!keyboard2',
        'this is my second mechanical keyboard: '
        'https://i.fluffy.cc/CDtRzWX1JZTbqzKswHrZsF7HPX2zfLL1.png',
    ),
    # the rest of these are sorted by command
    (
        '!discord',
        'We do have Discord, you are welcome to join: '
        'https://discord.gg/HxpQ3px',
    ),
    ('!emoji', 'anthon63DumpsterFire anthon63Pythonk'),
    (
        '!explain',
        'https://www.youtube.com/playlist?list=PLWBKAf81pmOaP9naRiNAqug6EBnkPakvY',  # noqa: E501
    ),
    (
        '!github',
        "anthony's github is https://github.com/asottile -- stream github is "
        'https://github.com/anthonywritescode',
    ),
    ('!homeland', 'WE WILL PROTECT OUR HOMELAND!'),
    (
        '!keyboard',
        'this is my streaming keyboard (contributed by PhillipWei): '
        'https://www.wasdkeyboards.com/code-v3-87-key-mechanical-keyboard-zealio-67g.html',  # noqa: E501
    ),
    ('!levelup', 'https://i.imgur.com/Uoq5vGx.gif'),
    ('!lurk', 'thanks for lurking, {user}!'),
    ('!ohai', 'ohai, {user}!'),
    ('!twitter', 'https://twitter.com/codewithanthony'),
    ('!water', 'DRINK WATER, BITCH'),
    ('!youtube', 'https://youtube.com/anthonywritescode'),
)


def _generic_msg_handler(match: Match[str], *, msg: str) -> Response:
    return MessageResponse(match, msg)


for _cmd, _msg in _TEXT_COMMANDS:
    handle_message(_cmd)(functools.partial(_generic_msg_handler, msg=_msg))


@handle_message('!still')
def cmd_still(match: Match[str]) -> Response:
    _, _, rest = match['msg'].partition(' ')
    year = datetime.date.today().year
    lol = random.choice(['LOL', 'LOLW', 'LMAO', 'NUUU'])
    return MessageResponse(match, f'{esc(rest)}, in {year} - {lol}!')


async def ensure_table_exists(db: aiosqlite.Connection) -> None:
    await db.execute(
        'CREATE TABLE IF NOT EXISTS today ('
        '   msg TEXT NOT NULL,'
        '   timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        ')',
    )
    await db.commit()


async def set_today(db: aiosqlite.Connection, msg: str) -> None:
    await ensure_table_exists(db)
    await db.execute('INSERT INTO today (msg) VALUES (?)', (msg,))
    await db.commit()


async def get_today(db: aiosqlite.Connection) -> str:
    await ensure_table_exists(db)
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


@handle_message('!today', '!project')
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


@handle_message('!settoday')
def cmd_settoday(match: Match[str]) -> Response:
    if match['user'] != match['channel']:
        return MessageResponse(
            match, 'https://www.youtube.com/watch?v=RfiQYRn7fBg',
        )
    _, _, rest = match['msg'].partition(' ')
    return SetTodayResponse(match, rest)


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


@handle_message('![wv]ideoidea')
def cmd_videoidea(match: Match[str]) -> Response:
    if match['user'] != match['channel']:
        return MessageResponse(
            match, 'https://www.youtube.com/watch?v=RfiQYRn7fBg',
        )
    _, _, rest = match['msg'].partition(' ')
    return VideoIdeaResponse(match, rest)


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

                parts = []
                for n, unit in (
                        (60 * 60, 'hours'),
                        (60, 'minutes'),
                        (1, 'seconds'),
                ):
                    if elapsed // n:
                        parts.append(f'{elapsed // n} {unit}')
                    elapsed %= n
                msg = f'streaming for: {", ".join(parts)}'
                return PRIVMSG.format(channel=config.channel, msg=msg)


@handle_message('!uptime')
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
@handle_message(r'!followage(?P<payload> .*)?')
def cmd_followage(match: Match[str]) -> Response:
    user = match['user']
    # "" is a default value if group is missing
    groupdict = match.groupdict('')
    payload = groupdict['payload'].strip()
    if payload:
        user = payload.lstrip('@')

    return FollowageResponse(user)


@handle_message(r'!pep[ ]?(?P<pep_num>\d{1,4})')
def cmd_pep(match: Match[str]) -> Response:
    n = str(int(match['pep_num'])).zfill(4)
    return MessageResponse(match, f'https://www.python.org/dev/peps/pep-{n}/')


@handle_message('!joke')
def cmd_joke(match: Match[str]) -> Response:
    return MessageResponse(match, esc(pyjokes.get_joke()))


COMMAND_RE = re.compile(r'!\w+')
SECRET_CMDS = frozenset(('!settoday',))


@handle_message(r'!\w')
def cmd_help(match: Match[str]) -> Response:
    possible = [COMMAND_RE.search(reg.pattern) for reg, _ in HANDLERS]
    possible_cmds = {match[0] for match in possible if match} - SECRET_CMDS
    commands = ['!help'] + sorted(possible_cmds)
    msg = f'possible commands: {", ".join(commands)}'
    if not match['msg'].startswith('!help'):
        msg = f'unknown command ({esc(match["msg"].split()[0])}), {msg}'
    return MessageResponse(match, msg)


@handle_message('PING')
def msg_ping(match: Match[str]) -> Response:
    _, _, rest = match['msg'].partition(' ')
    return MessageResponse(match, f'PONG {esc(rest)}')


@handle_message(r'.*\b(nano|linux|windows|emacs)\b', flags=re.IGNORECASE)
def msg_gnu_please(match: Match[str]) -> Response:
    msg, word = match[3], match[4]
    query = re.search(f'gnu[/+]{word}', msg, flags=re.IGNORECASE)
    if query:
        return MessageResponse(match, f'YES! {query[0]}')
    else:
        return MessageResponse(match, f"Um please, it's GNU+{esc(word)}!")


@handle_message(r'.*\bth[oi]nk(?:ing)?\b', flags=re.IGNORECASE)
def msg_think(match: Match[str]) -> Response:
    return MessageResponse(match, 'anthon63Pythonk ' * 5)


# TODO: !tags, only allowed by stream admin / mods????

def dt_str() -> str:
    dt_now = datetime.datetime.now()
    return f'[{dt_now.hour:02}:{dt_now.minute:02}]'


async def amain(config: Config, *, quiet: bool) -> NoReturn:
    reader, writer = await asyncio.open_connection(HOST, PORT, ssl=True)

    await send(writer, f'PASS {config.oauth_token}\r\n', quiet=True)
    await send(writer, f'NICK {config.username}\r\n', quiet=quiet)
    await send(writer, f'JOIN #{config.channel}\r\n', quiet=quiet)
    await send(writer, 'CAP REQ :twitch.tv/tags\r\n', quiet=quiet)

    while True:
        data = await recv(reader, quiet=quiet)
        msg = data.decode('UTF-8', errors='backslashreplace')

        msg_match = MSG_RE.match(msg)
        if msg_match:
            info = _parse_badge_info(msg_match[1])
            if info['color']:
                r, g, b = _parse_color(info['color'])
            else:
                r, g, b = _gen_color(info['display-name'])

            color_start = f'\033[1m\033[38;2;{r};{g};{b}m'

            if msg_match[3].startswith('\x01ACTION '):
                print(
                    f'{dt_str()}'
                    f'{_badges(info["badges"])}'
                    f'{color_start}\033[3m * {info["display-name"]}\033[22m '
                    f'{msg_match[3][8:-1]}\033[m',
                )
            else:
                print(
                    f'{dt_str()}'
                    f'{_badges(info["badges"])}'
                    f'<{color_start}{info["display-name"]}\033[m> '
                    f'{msg_match[3]}',
                )

        for pattern, handler in HANDLERS:
            match = pattern.match(msg)
            if match:
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
                        print(
                            f'{dt_str()}'
                            f'<{color}{config.username}\033[m> '
                            f'{send_match[1]}',
                        )
                    await send(writer, res, quiet=quiet)
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

    asyncio.run(amain(config, quiet=not args.verbose))
    return 0


if __name__ == '__main__':
    exit(main())
