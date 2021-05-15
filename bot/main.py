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

from bot.badges import badges_images
from bot.badges import badges_plain_text
from bot.badges import download_all_badges
from bot.badges import parse_badges
from bot.config import Config
from bot.data import Callback
from bot.data import get_fake_msg
from bot.data import get_handler
from bot.data import MSG_RE
from bot.data import PERIODIC_HANDLERS
from bot.data import PRIVMSG
from bot.emote import download_all_emotes
from bot.emote import parse_emote_info
from bot.emote import replace_emotes
from bot.permissions import parse_badge_info

# TODO: allow host / port to be configurable
HOST = 'irc.chat.twitch.tv'
PORT = 6697

SEND_MSG_RE = re.compile('^PRIVMSG #[^ ]+ :(?P<msg>[^\r]+)')


def _parse_color(s: str) -> tuple[int, int, int]:
    return int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16)


def _gen_color(name: str) -> tuple[int, int, int]:
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
        shutdown_task: asyncio.Task[Any] | None = None,
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
        uncolored_msg = UNCOLOR_RE.sub('', msg)
        os.makedirs('logs', exist_ok=True)
        log = os.path.join('logs', f'{self.date}.log')
        with open(log, 'a+', encoding='UTF-8') as f:
            f.write(f'{uncolored_msg}\n')


def get_printed_output(config: Config, res: str) -> str | None:
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
        res = await handler(config, match)
    except Exception as e:
        traceback.print_exc()
        res = PRIVMSG.format(
            channel=config.channel,
            msg=f'*** unhandled {type(e).__name__} -- see logs',
        )
    if res is not None:
        printed_output = get_printed_output(config, res)
        if printed_output is not None:
            print(printed_output)
            log_writer.write_message(printed_output)
        await send(writer, res, quiet=quiet)


def _start_periodic(
        config: Config,
        writer: asyncio.StreamWriter,
        log_writer: LogWriter,
        *,
        quiet: bool,
) -> None:
    async def periodic(minutes: int, func: Callback) -> None:
        line = get_fake_msg(config, 'placeholder message')
        match = MSG_RE.match(line)
        assert match is not None
        while True:
            await asyncio.sleep(minutes * 60)
            await handle_response(
                config, match, func, writer, log_writer, quiet=quiet,
            )

    loop = asyncio.get_event_loop()
    for minutes, func in PERIODIC_HANDLERS:
        loop.create_task(periodic(minutes, func))


async def get_printed_input(
        config: Config,
        msg: str,
        *,
        images: bool,
) -> tuple[str, str] | None:
    msg_match = MSG_RE.match(msg)
    if msg_match:
        info = parse_badge_info(msg_match['info'])
        if info['color']:
            r, g, b = _parse_color(info['color'])
        else:
            r, g, b = _gen_color(info['display-name'])

        color_start = f'\033[1m\033[38;2;{r};{g};{b}m'

        msg_s = msg_match['msg']
        is_action = msg_s.startswith('\x01ACTION ')
        if is_action:
            msg_s = msg_s[8:-1]

        badges_s = badges_plain_text(info['badges'])
        if images:
            badges = parse_badges(info['badges'])
            await download_all_badges(
                badges,
                channel=config.channel,
                oauth_token=config.oauth_token_token,
                client_id=config.client_id,
            )
            badges_s_images = badges_images(badges)
        else:
            badges_s_images = badges_s

        if images:
            emote_info = parse_emote_info(info['emotes'])
            await download_all_emotes(emote_info)
            msg_s_images = replace_emotes(msg_s, emote_info)
        else:
            msg_s_images = msg_s

        if is_action:
            fmt = (
                f'{dt_str()}'
                f'{{badges}}'
                f'{color_start}\033[3m * {info["display-name"]}\033[22m '
                f'{{msg}}\033[m'
            )
        elif info.get('msg-id') == 'highlighted-message':
            fmt = (
                f'{dt_str()}'
                f'{{badges}}'
                f'<{color_start}{info["display-name"]}\033[m> '
                f'\033[48;2;117;094;188m{{msg}}\033[m'
            )
        elif 'custom-reward-id' in info:
            fmt = (
                f'{dt_str()}'
                f'{{badges}}'
                f'<{color_start}{info["display-name"]}\033[m> '
                f'\033[48;2;029;091;130m{{msg}}\033[m'
            )
        else:
            fmt = (
                f'{dt_str()}'
                f'{{badges}}'
                f'<{color_start}{info["display-name"]}\033[m> '
                f'{{msg}}'
            )

        to_print = fmt.format(badges=badges_s_images, msg=msg_s_images)
        to_log = fmt.format(badges=badges_s, msg=msg_s)
        return to_print, to_log

    return None


async def amain(config: Config, *, quiet: bool, images: bool) -> None:
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

    _start_periodic(config, writer, log_writer, quiet=quiet)

    while not writer.is_closing():
        data = await recv(reader, quiet=quiet)
        if not data:
            return
        msg = data.decode('UTF-8', errors='backslashreplace')

        input_ret = await get_printed_input(config, msg, images=images)
        if input_ret is not None:
            to_print, to_log = input_ret
            print(to_print)
            log_writer.write_message(to_log)

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
    line = get_fake_msg(config, msg)

    input_ret = await get_printed_input(config, line, images=False)
    assert input_ret is not None
    to_print, _ = input_ret
    print(to_print)

    maybe_handler_match = get_handler(line)
    if maybe_handler_match is not None:
        handler, match = maybe_handler_match
        result = await handler(config, match)
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
    parser.add_argument('--images', action='store_true')
    parser.add_argument('--test')
    args = parser.parse_args()

    quiet = not args.verbose

    with open(args.config) as f:
        config = Config(**json.load(f))

    if args.test:
        asyncio.run(chat_message_test(config, args.test))
    else:
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(amain(config, quiet=quiet, images=args.images))

    return 0


if __name__ == '__main__':
    exit(main())
