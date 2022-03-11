from __future__ import annotations

import asyncio
import io
import json
import os.path
import plistlib
import re
import uuid
from typing import Any
from typing import Match

import aiohttp
import cson
import defusedxml.ElementTree

from bot.config import Config
from bot.data import channel_points_handler
from bot.data import command
from bot.data import esc
from bot.data import format_msg

ALLOWED_URL_PREFIXES = (
    'https://gist.github.com/',
    'https://gist.githubusercontent.com/',
    'https://github.com/',
    'https://raw.githubusercontent.com/',
)

COMMENT_TOKEN = re.compile(br'(\\\\|\\"|"|//|\n)')
COMMA_TOKEN = re.compile(br'(\\\\|\\"|"|\]|\})')
TRAILING_COMMA = re.compile(br',(\s*)$')

THEME_DIR = os.path.abspath('.babi-themes')


def _remove_comments(s: bytes) -> io.BytesIO:
    bio = io.BytesIO()

    idx = 0
    in_string = False
    in_comment = False

    match = COMMENT_TOKEN.search(s, idx)
    while match:
        if not in_comment:
            bio.write(s[idx:match.start()])

        tok = match[0]
        if not in_comment and tok == b'"':
            in_string = not in_string
        elif in_comment and tok == b'\n':
            in_comment = False
        elif not in_string and tok == b'//':
            in_comment = True

        if not in_comment:
            bio.write(tok)

        idx = match.end()
        match = COMMENT_TOKEN.search(s, idx)
    bio.write(s[idx:])

    return bio


def _remove_trailing_commas(s: bytes) -> io.BytesIO:
    bio = io.BytesIO()

    idx = 0
    in_string = False

    match = COMMA_TOKEN.search(s, idx)
    while match:
        tok = match[0]
        if tok == b'"':
            in_string = not in_string
            bio.write(s[idx:match.start()])
            bio.write(tok)
        elif in_string:
            bio.write(s[idx:match.start()])
            bio.write(tok)
        elif tok in b']}':
            bio.write(TRAILING_COMMA.sub(br'\1', s[idx:match.start()]))
            bio.write(tok)
        else:
            bio.write(s[idx:match.start()])
            bio.write(tok)

        idx = match.end()
        match = COMMA_TOKEN.search(s, idx)
    bio.write(s[idx:])

    return bio


def json_with_comments(s: bytes) -> Any:
    bio = _remove_comments(s)
    bio = _remove_trailing_commas(bio.getvalue())

    bio.seek(0)
    return json.load(bio)


def safe_ish_plist_loads(s: bytes) -> Any:
    # try and parse it using `defusedxml` first to make sure it's "safe"
    defusedxml.ElementTree.fromstring(s)
    return plistlib.loads(s)


STRATEGIES = (json.loads, safe_ish_plist_loads, cson.loads, json_with_comments)


def _validate_color(color: Any) -> None:
    if not isinstance(color, str):
        raise TypeError

    if color in {'black', 'white'}:
        return
    if not color.startswith('#'):
        raise ValueError

    # raises ValueError if incorrect
    int(color[1:], 16)


def _validate_theme(theme: Any) -> None:
    if (
            not isinstance(theme, dict) or
            not isinstance(theme.get('colors', {}), dict) or
            not isinstance(theme.get('tokenColors', []), list) or
            not isinstance(theme.get('settings', []), list)
    ):
        raise TypeError

    colors_dct = theme.get('colors', {})
    for key in (
        'background',
        'foreground',
        'editor.foreground',
        'editor.background',
    ):
        if key in colors_dct:
            _validate_color(colors_dct[key])

    for rule in theme.get('tokenColors', []) + theme.get('settings', []):
        if not isinstance(rule, dict):
            raise TypeError
        for key in ('background', 'foreground'):
            if key in rule:
                _validate_color(rule[key])


@channel_points_handler('5861c27a-ae1f-4b8e-af03-88f12dd7d23a')
async def change_theme(config: Config, match: Match[str]) -> str:
    url = match['msg'].strip()
    if not url.startswith(ALLOWED_URL_PREFIXES):
        return format_msg(match, 'error: url must be from github!')

    if '/blob/' in url:
        url = url.replace('/blob/', '/raw/')

    try:
        async with aiohttp.ClientSession(
                raise_for_status=True,
                read_timeout=2,
        ) as session:
            async with session.get(url) as resp:
                data = await resp.read()
    except aiohttp.ClientError:
        return format_msg(match, 'error: could not download url!')

    for strategy in STRATEGIES:
        try:
            loaded = strategy(data)
        except Exception:
            pass
        else:
            break
    else:
        return format_msg(match, 'error: could not parse theme!')

    try:
        _validate_theme(loaded)
    except (TypeError, ValueError):
        return format_msg(match, 'error: malformed theme!')

    loaded['user'] = match['user']
    loaded['url'] = url

    os.makedirs(THEME_DIR, exist_ok=True)
    theme_file = f'{match["user"]}-{uuid.uuid4()}.json'
    theme_file = os.path.join(THEME_DIR, theme_file)
    with open(theme_file, 'w') as f:
        json.dump(loaded, f)

    themedir = os.path.expanduser('~/.config/babi')
    os.makedirs(themedir, exist_ok=True)

    dest = os.path.join(themedir, 'theme.json')
    proc = await asyncio.create_subprocess_exec('ln', '-sf', theme_file, dest)
    await proc.communicate()
    assert proc.returncode == 0

    proc = await asyncio.create_subprocess_exec('pkill', '-USR1', 'babi')
    await proc.communicate()
    # ignore the return code, if there are no editors running it'll be `1`
    # assert proc.returncode == 0

    return format_msg(match, 'theme updated!')


@command('!theme')
async def command_theme(config: Config, match: Match[str]) -> str:
    theme_file = os.path.expanduser('~/.config/babi/theme.json')
    if not os.path.exists(theme_file):
        return format_msg(
            match,
            'awcBabi this is vs dark plus in !babi with one modification to '
            'highlight ini headers: '
            'https://github.com/asottile/babi#setting-up-syntax-highlighting',
        )

    with open(theme_file) as f:
        contents = json.load(f)

    try:
        name = contents.get('name', '(unknown)')
        user = contents['user']
        url = contents['url']
    except KeyError:
        return format_msg(match, "awcBabi I don't know what this theme is!?")
    else:
        return format_msg(
            match,
            f'awcBabi this theme was set by {esc(user)} using channel points! '
            f'it is called {esc(name)!r} and can be download from {esc(url)}',
        )
