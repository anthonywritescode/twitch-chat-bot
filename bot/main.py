from __future__ import annotations

import argparse
import asyncio.subprocess
import contextlib
import datetime
import functools
import json
import os.path
import re
import signal
import sys
import traceback
from collections.abc import AsyncGenerator

from bot.badges import badges_images
from bot.badges import badges_plain_text
from bot.badges import download_all_badges
from bot.badges import parse_badges
from bot.config import Config
from bot.data import Callback
from bot.data import get_fake_msg
from bot.data import get_handler
from bot.data import PERIODIC_HANDLERS
from bot.data import PRIVMSG
from bot.message import Message
from bot.parse_message import parse_message_parts
from bot.parse_message import parsed_to_terminology

# TODO: allow host / port to be configurable
HOST = 'irc.chat.twitch.tv'
PORT = 6697

SEND_MSG_RE = re.compile('^PRIVMSG #[^ ]+ :(?P<msg>[^\r]+)')


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


def _shutdown(
        writer: asyncio.StreamWriter,
        loop: asyncio.AbstractEventLoop,
) -> None:
    print('bye!')

    if writer:
        writer.close()
        loop.create_task(writer.wait_closed())


async def connect(
        config: Config,
        *,
        quiet: bool,
) -> tuple[AsyncGenerator[bytes, None], asyncio.StreamWriter]:
    async def _new_conn() -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        reader, writer = await asyncio.open_connection(HOST, PORT, ssl=True)

        loop = asyncio.get_event_loop()
        shutdown_cb = functools.partial(_shutdown, writer, loop)
        try:
            loop.add_signal_handler(signal.SIGINT, shutdown_cb)
        except NotImplementedError:
            # Doh... Windows...
            signal.signal(signal.SIGINT, lambda *_: shutdown_cb())

        await send(writer, 'CAP REQ :twitch.tv/tags\r\n', quiet=quiet)
        await send(writer, f'PASS {config.oauth_token}\r\n', quiet=True)
        await send(writer, f'NICK {config.username}\r\n', quiet=quiet)
        await send(writer, f'JOIN #{config.channel}\r\n', quiet=quiet)

        return reader, writer

    reader, writer = await _new_conn()

    async def next_line() -> AsyncGenerator[bytes, None]:
        nonlocal reader, writer

        while not writer.is_closing():
            data = await recv(reader, quiet=quiet)
            if not data:
                if writer.is_closing():
                    return
                else:
                    print('!!!reconnect!!!')
                    reader, writer = await _new_conn()
                    continue

            yield data

    return next_line(), writer


# TODO: !tags, only allowed by stream admin / mods????

def dt_str() -> str:
    dt_now = datetime.datetime.now()
    return f'[{dt_now.hour:02}:{dt_now.minute:02}]'


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
        msg: Message,
        handler: Callback,
        writer: asyncio.StreamWriter,
        log_writer: LogWriter,
        *,
        quiet: bool,
) -> None:
    try:
        res = await handler(config, msg)
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
    async def periodic(seconds: int, func: Callback) -> None:
        msg = Message(
            msg='placeholder',
            is_me=False,
            channel=config.channel,
            info={'display-name': config.username},
        )
        while True:
            await asyncio.sleep(seconds)
            await handle_response(
                config, msg, func, writer, log_writer, quiet=quiet,
            )

    loop = asyncio.get_event_loop()
    for seconds, func in PERIODIC_HANDLERS:
        loop.create_task(periodic(seconds, func))


async def get_printed_input(
        config: Config,
        msg: str,
        *,
        images: bool,
) -> tuple[str, str] | None:
    parsed = Message.parse(msg)
    if parsed:
        r, g, b = parsed.color
        color_start = f'\033[1m\033[38;2;{r};{g};{b}m'

        badges_s = badges_plain_text(parsed.badges)
        if images:
            # TODO: maybe combine into `Message`?
            badges = parse_badges(parsed.info['badges'])
            await download_all_badges(
                parse_badges(parsed.info['badges']),
                channel=config.channel,
                oauth_token=config.oauth_token_token,
                client_id=config.client_id,
            )
            badges_s_images = badges_images(badges)
        else:
            badges_s_images = badges_s

        if images:
            big = parsed.info.get('msg-id') == 'gigantified-emote-message'
            msg_parsed = await parse_message_parts(
                msg=parsed,
                channel=config.channel,
                oauth_token=config.oauth_token_token,
                client_id=config.client_id,
            )
            msg_s_images = await parsed_to_terminology(msg_parsed, big=big)
        else:
            msg_s_images = parsed.msg

        if parsed.is_me:
            fmt = (
                f'{dt_str()}'
                f'{{badges}}'
                f'{color_start}\033[3m * {parsed.display_name}\033[22m '
                f'{{msg}}\033[m'
            )
        elif parsed.bg_color is not None:
            bg_color_s = '{};{};{}'.format(*parsed.bg_color)
            fmt = (
                f'{dt_str()}'
                f'{{badges}}'
                f'<{color_start}{parsed.display_name}\033[m> '
                f'\033[48;2;{bg_color_s}m{{msg}}\033[m'
            )
        else:
            fmt = (
                f'{dt_str()}'
                f'{{badges}}'
                f'<{color_start}{parsed.display_name}\033[m> '
                f'{{msg}}'
            )

        to_print = fmt.format(badges=badges_s_images, msg=msg_s_images)
        to_log = fmt.format(badges=badges_s, msg=parsed.msg)
        return to_print, to_log

    return None


async def amain(config: Config, *, quiet: bool, images: bool) -> None:
    log_writer = LogWriter()
    line_iter, writer = await connect(config, quiet=quiet)

    _start_periodic(config, writer, log_writer, quiet=quiet)

    async for data in line_iter:
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
            asyncio.get_event_loop().create_task(coro)
        elif msg.startswith('PING '):
            _, _, rest = msg.partition(' ')
            await send(writer, f'PONG {rest.rstrip()}\r\n', quiet=quiet)
        elif not quiet:
            print(f'UNHANDLED: {msg}', end='')


async def chat_message_test(
        config: Config,
        msg: str,
        *,
        bits: int,
        mod: bool,
        user: str,
) -> None:
    line = get_fake_msg(config, msg, bits=bits, mod=mod, user=user)

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
    parser.add_argument('--user', default='username')
    parser.add_argument('--bits', type=int, default=0)
    parser.add_argument('--mod', action='store_true')
    args = parser.parse_args()

    quiet = not args.verbose

    with open(args.config) as f:
        config = Config(**json.load(f))

    if args.test:
        asyncio.run(
            chat_message_test(
                config,
                args.test,
                bits=args.bits,
                mod=args.mod,
                user=args.user,
            ),
        )
    else:
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(amain(config, quiet=quiet, images=args.images))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
