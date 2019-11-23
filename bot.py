import argparse
import asyncio
import datetime
import json
import random
import re
import sys
import traceback
from typing import Callable
from typing import List
from typing import Match
from typing import NamedTuple
from typing import NoReturn
from typing import Optional
from typing import Pattern
from typing import Tuple

import aiohttp
import aiosqlite

# TODO: allow host / port to be configurable
HOST = 'irc.chat.twitch.tv'
PORT = 6697


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


PRIVMSG = 'PRIVMSG #{channel} :{msg}\r\n'


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
            f'^:(?P<user>[^!]+).* '
            f'PRIVMSG #(?P<channel>[^ ]+) '
            f':(?P<msg>{message_prefix}.*)'
            for message_prefix in message_prefixes
        ), flags=flags,
    )


@handler('^PING (.*)')
def pong(match: Match[str]) -> Response:
    return CmdResponse(f'PONG {match.group(1)}\r\n')


@handle_message('!ohai')
def cmd_ohai(match: Match[str]) -> Response:
    return MessageResponse(match, 'ohai, {user}!')


@handle_message('!lurk')
def cmd_lurk(match: Match[str]) -> Response:
    return MessageResponse(match, 'thanks for lurking, {user}!')


@handle_message('!discord')
def cmd_discord(match: Match[str]) -> Response:
    return MessageResponse(
        match,
        'We do have Discord, you are welcome to join: '
        'https://discord.gg/HxpQ3px',
    )


@handle_message('!homeland')
def cmd_russians(match: Match[str]) -> Response:
    return MessageResponse(match, 'WE WILL PROTECT OUR HOMELAND!')


@handle_message('!emoji')
def cmd_emoji(match: Match[str]) -> Response:
    return MessageResponse(match, 'anthon63DumpsterFire anthon63Pythonk')


@handle_message('!keyboard2')
def keyboard2(match: Match[str]) -> Response:
    return MessageResponse(
        match,
        'this is my second mechanical keyboard: '
        'https://i.fluffy.cc/CDtRzWX1JZTbqzKswHrZsF7HPX2zfLL1.png',
    )


@handle_message('!keyboard')
def keyboard(match: Match[str]) -> Response:
    return MessageResponse(
        match,
        'this is my streaming keyboard (contributed by PhillipWei): '
        'https://www.wasdkeyboards.com/code-v3-87-key-mechanical-keyboard-zealio-67g.html',  # noqa: E501
    )


@handle_message('!github')
def github(match: Match[str]) -> Response:
    return MessageResponse(
        match,
        "anthony's github is https://github.com/asottile -- stream github is "
        "https://github.com/anthonywritescode",
    )


@handle_message('!still')
def cmd_still(match: Match[str]) -> Response:
    _, _, msg = match.groups()
    _, _, rest = msg.partition(' ')
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
    _, _, msg = match.groups()
    _, _, rest = msg.partition(' ')
    return SetTodayResponse(match, rest)


class UptimeResponse(Response):
    async def __call__(self, config: Config) -> Optional[str]:
        url = f'https://api.twitch.tv/helix/streams?user_login={config.channel}'  # noqa: E501
        headers = {'Client-ID': config.client_id}
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


@handle_message(r'!pep[ ]?(?P<pep_num>\d{1,4})', flags=re.ASCII)
def cmd_pep(match: Match[str]) -> Response:
    *_, number = match.groups()
    return MessageResponse(
        match, f'https://www.python.org/dev/peps/pep-{number.zfill(4)}/',
    )


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
    _, _, msg = match.groups()
    _, _, rest = msg.partition(' ')
    return MessageResponse(match, f'PONG {esc(rest)}')


@handle_message(r'.*\b(nano|linux|windows|emacs)\b', flags=re.IGNORECASE)
def msg_gnu_please(match: Match[str]) -> Response:
    msg, word = match[3], match[4]
    query = re.search(f'gnu[/+]{word}', msg, flags=re.IGNORECASE)
    if query:
        return MessageResponse(match, f'YES! {query[0]}')
    else:
        return MessageResponse(match, f"Um please, it's GNU+{esc(word)}!")


# TODO: !tags, only allowed by stream admin / mods????


@handler('.*')
def unhandled(match: Match[str]) -> Response:
    print(f'UNHANDLED: {match.group()}', end='')
    return Response()


async def amain(config: Config) -> NoReturn:
    reader, writer = await asyncio.open_connection(HOST, PORT, ssl=True)

    await send(writer, f'PASS {config.oauth_token}\r\n', quiet=True)
    await send(writer, f'NICK {config.username}\r\n')
    await send(writer, f'JOIN #{config.channel}\r\n')

    while True:
        data = await recv(reader)
        msg = data.decode('UTF-8', errors='backslashreplace')
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
                    await send(writer, res)
                break


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.json')
    args = parser.parse_args()

    with open(args.config) as f:
        config = Config(**json.load(f))

    asyncio.run(amain(config))
    return 0


if __name__ == '__main__':
    exit(main())
