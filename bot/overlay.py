from __future__ import annotations

import argparse
import asyncio
import collections
import contextlib
import json
import re

import aiohttp.web
import websockets.exceptions
import websockets.server
from websockets.server import WebSocketServerProtocol

from bot.badges import all_badges
from bot.badges import parse_badges
from bot.config import Config
from bot.message import Message
from bot.parse_message import parse_message_parts
from bot.parse_message import parsed_to_overlay

WSS_URL = 'wss://irc-ws.chat.twitch.tv:443'
ALLOWED_HOST = re.compile(r'^(localhost|\d+(\.\d+){3})$', re.ASCII)


class GuardedDeque:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._deque: collections.deque[Message] = collections.deque(maxlen=20)

    async def append(self, message: Message) -> None:
        async with self._lock:
            self._deque.append(message)

    async def copy(self) -> tuple[Message, ...]:
        async with self._lock:
            return tuple(self._deque)


def _html_color(color: tuple[int, int, int] | None) -> str | None:
    if color is not None:
        return '#{:02x}{:02x}{:02x}'.format(*color)
    else:
        return None


async def index(request: aiohttp.web.Request) -> aiohttp.web.Response:
    hostname, _, _ = request.host.partition(':')
    if not ALLOWED_HOST.match(hostname):
        return aiohttp.web.Response(status=403)
    with open('overlay/index.htm') as f:
        contents = f.read()
    contents = contents.replace('ws://localhost', f'ws://{hostname}')
    return aiohttp.web.Response(text=contents, content_type='text/html')


async def http_server() -> None:
    app = aiohttp.web.Application()
    app.router.add_route('GET', '/', index)

    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, '0.0.0.0', 9001)
    await site.start()

    await asyncio.Future()  # run forever


async def _write_to_readers(
        messages: asyncio.Queue[Message],
        buffer: GuardedDeque,
        readers: list[asyncio.Queue[Message]],
) -> None:
    while True:
        msg = await messages.get()
        await buffer.append(msg)
        await asyncio.gather(*[reader.put(msg) for reader in readers])


async def _ws_server(
        config: Config,
        buffer: GuardedDeque,
        readers: list[asyncio.Queue[Message]],
) -> None:
    async def _cb(websocket: WebSocketServerProtocol) -> None:
        print('starting')
        queue: asyncio.Queue[Message] = asyncio.Queue()
        readers.append(queue)

        async def _send(msg: Message) -> None:
            badge_urls = await all_badges(
                config.channel,
                oauth_token=config.oauth_token_token,
                client_id=config.client_id,
            )
            badges = parse_badges(msg.info['badges'])

            msg_parsed = await parse_message_parts(
                msg=msg,
                channel=config.channel,
                oauth_token=config.oauth_token_token,
                client_id=config.client_id,
            )

            parts = parsed_to_overlay(msg_parsed)

            data = {
                'badges': [
                    badge_urls[badge.badge][badge.version]
                    for badge in badges
                ],
                'is_me': msg.is_me,
                'color': _html_color(msg.color),
                'bg_color': _html_color(msg.bg_color),
                'user': msg.display_name,
                'parts': parts,
            }
            await websocket.send(json.dumps(data))

        try:
            for msg in await buffer.copy():
                await _send(msg)

            print('started')
            while True:
                msg = await queue.get()
                await _send(msg)
        except websockets.exceptions.ConnectionClosedOK:
            pass  # ignore graceful close
        finally:
            print('bai')
            readers.remove(queue)

    async with websockets.server.serve(_cb, '0.0.0.0', 9002):
        await asyncio.Future()  # run forever


async def websocket_server(
        config: Config,
        messages: asyncio.Queue[Message],
) -> None:
    buffer = GuardedDeque()
    readers: list[asyncio.Queue[Message]] = []

    await asyncio.gather(
        _write_to_readers(messages, buffer, readers),
        _ws_server(config, buffer, readers),
    )


async def chatbot(
        config: Config,
        messages: asyncio.Queue[Message],
) -> None:
    async for websocket in websockets.connect(WSS_URL):
        try:
            await websocket.send('CAP REQ :twitch.tv/tags')
            await websocket.send(f'PASS {config.oauth_token}')
            await websocket.send(f'NICK {config.username}')
            await websocket.send(f'JOIN #{config.channel}')

            async for msg in websocket:
                parsed = Message.parse(msg)
                if parsed is not None:
                    await messages.put(parsed)
                elif msg.startswith('PING '):
                    _, _, rest = msg.partition(' ')
                    await websocket.send(f'PONG {rest}')
        except websockets.ConnectionClosed:
            print('!!!reconnect!!!')
            continue


async def amain(config: Config) -> None:
    messages: asyncio.Queue[Message] = asyncio.Queue()

    loop = asyncio.get_event_loop()
    loop.create_task(http_server())
    loop.create_task(websocket_server(config, messages))

    await chatbot(config, messages)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.json')
    args = parser.parse_args()

    with open(args.config) as f:
        config = Config(**json.load(f))

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(amain(config))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
