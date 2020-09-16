from __future__ import annotations

import argparse
import asyncio.subprocess
import contextlib
import datetime
import functools
import hashlib
import json
import os.path
import re
import signal
import struct
import sys
import traceback
from typing import Any
from typing import Match
from typing import Optional
from typing import Tuple

from bot.config import Config
from bot.data import Callback
from bot.data import get_handler
from bot.data import MSG_RE
from bot.data import PRIVMSG
from bot.permissions import parse_badge_info

# TODO: allow host / port to be configurable
HOST = 'irc.chat.twitch.tv'
PORT = 6697

SEND_MSG_RE = re.compile('^PRIVMSG #[^ ]+ :(?P<msg>[^\r]+)')


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
    if not quiet:
        sys.stderr.buffer.write(b'> ')
        sys.stderr.buffer.write(data)
        sys.stderr.flush()
    return data


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


def get_printed_output(config: Config, res: str) -> Optional[str]:
    send_match = SEND_MSG_RE.match(res)
    if send_match:
        color = '\033[1m\033[3m\033[38;5;21m'
        return (
            f'{dt_str()}'
            f'<{color}{config.username}\033[m> '
            f'{send_match[1]}'
        )
    else:
        return None


async def handle_response(
        config: Config,
        match: Match[str],
        handler: Callback,
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
        printed_output = get_printed_output(config, res)
        if printed_output is not None:
            log_writer.write_message(printed_output)
        await send(writer, res, quiet=quiet)


def get_printed_input(msg: str) -> Optional[str]:
    msg_match = MSG_RE.match(msg)
    if msg_match:
        info = parse_badge_info(msg_match['info'])
        if info['color']:
            r, g, b = _parse_color(info['color'])
        else:
            r, g, b = _gen_color(info['display-name'])

        color_start = f'\033[1m\033[38;2;{r};{g};{b}m'

        if msg_match['msg'].startswith('\x01ACTION '):
            return (
                f'{dt_str()}'
                f'{_badges(info["badges"])}'
                f'{color_start}\033[3m * {info["display-name"]}\033[22m '
                f'{msg_match["msg"][8:-1]}\033[m'
            )
        else:
            if info.get('msg-id') == 'highlighted-message':
                msg_s = f'\033[48;2;117;094;188m{msg_match["msg"]}\033[m'
            elif 'custom-reward-id' in info:
                msg_s = f'\033[48;2;029;091;130m{msg_match["msg"]}\033[m'
            else:
                msg_s = msg_match['msg']

            return (
                f'{dt_str()}'
                f'{_badges(info["badges"])}'
                f'<{color_start}{info["display-name"]}\033[m> '
                f'{msg_s}'
            )

    return None


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

        printed_input = get_printed_input(msg)
        if printed_input is not None:
            log_writer.write_message(printed_input)

        maybe_handler_match = get_handler(msg)
        if maybe_handler_match is not None:
            handler, match = maybe_handler_match
            coro = handle_response(
                config, match, handler, writer, log_writer, quiet=quiet,
            )
            loop.create_task(coro)
        elif not quiet:
            print(f'UNHANDLED: {msg}', end='')


async def chat_message_test(config: Config, msg: str) -> None:
    info = '@color=;display-name=username;badges='
    line = f'{info} :username PRIVMSG #{config.channel} :{msg}\r\n'

    printed_input = get_printed_input(line)
    assert printed_input is not None
    print(printed_input)

    maybe_handler_match = get_handler(line)
    if maybe_handler_match is not None:
        handler, match = maybe_handler_match
        result = await handler(match)(config)
        if result is not None:
            printed_output = get_printed_output(config, result)
            if printed_output is not None:
                print(printed_output)
            else:
                print(result)
        else:
            print('<<handler returned None>>')
    else:
        print('<<no handler>>')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--test')
    args = parser.parse_args()

    with open(args.config) as f:
        config = Config(**json.load(f))

    if args.test:
        asyncio.run(chat_message_test(config, args.test))
    else:
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(amain(config, quiet=not args.verbose))

    return 0


if __name__ == '__main__':
    exit(main())
