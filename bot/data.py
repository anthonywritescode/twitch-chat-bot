from __future__ import annotations

import difflib
import pkgutil
import re
from typing import Awaitable
from typing import Callable
from typing import Match
from typing import Optional
from typing import Pattern

from bot import plugins
from bot.config import Config
from bot.permissions import parse_badge_info

# TODO: maybe move this?
PRIVMSG = 'PRIVMSG #{channel} : {msg}\r\n'
COMMAND_PATTERN_RE = re.compile(r'!+\w+')
MSG_RE = re.compile(
    '^@(?P<info>[^ ]+) :(?P<user>[^!]+).* '
    'PRIVMSG #(?P<channel>[^ ]+) '
    ':(?P<msg>[^\r]+)',
)
COMMAND_RE = re.compile(r'^(?P<cmd>!+\w+)')


def get_fake_msg(
        config: Config,
        msg: str,
        *,
        bits: int = 0,
        mod: bool = False,
        user: str = 'username',
) -> str:
    badges = 'moderator/1' if mod else ''
    info = f'@badges={badges};bits={bits};color=;display-name={user}'
    return f'{info} :{user} PRIVMSG #{config.channel} :{msg}\r\n'


# TODO: move this and/or delete this
def esc(s: str) -> str:
    return s.replace('{', '{{').replace('}', '}}')


def format_msg(match: Match[str], fmt: str) -> str:
    params = match.groupdict()
    params['msg'] = fmt.format(**params)
    return PRIVMSG.format(**params)


Callback = Callable[[Config, Match[str]], Awaitable[Optional[str]]]
HANDLERS: list[tuple[Pattern[str], Callback]] = []
COMMANDS: dict[str, Callback] = {}
POINTS_HANDLERS: dict[str, Callback] = {}
BITS_HANDLERS: dict[int, Callback] = {}
SECRET_CMDS: set[str] = set()
PERIODIC_HANDLERS: list[tuple[int, Callback]] = []


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


def bits_handler(bits_mod: int) -> Callable[[Callback], Callback]:
    def bits_handler_decorator(func: Callback) -> Callback:
        BITS_HANDLERS[bits_mod] = func
        return func
    return bits_handler_decorator


def add_alias(cmd: str, *aliases: str) -> None:
    for alias in aliases:
        COMMANDS[alias] = COMMANDS[cmd]
        SECRET_CMDS.add(alias)


def periodic_handler(*, seconds: int) -> Callable[[Callback], Callback]:
    def periodic_handler_decorator(func: Callback) -> Callback:
        PERIODIC_HANDLERS.append((seconds, func))
        return func
    return periodic_handler_decorator


def get_handler(msg: str) -> tuple[Callback, Match[str]] | None:
    msg_match = MSG_RE.match(msg)
    if msg_match:
        info = parse_badge_info(msg_match['info'])

        if 'custom-reward-id' in info:
            if info['custom-reward-id'] in POINTS_HANDLERS:
                return POINTS_HANDLERS[info['custom-reward-id']], msg_match
            else:
                return None

        if 'bits' in info:
            bits_n = int(info['bits'])
            if bits_n % 100 in BITS_HANDLERS:
                return BITS_HANDLERS[bits_n % 100], msg_match

        cmd_match = COMMAND_RE.match(msg_match['msg'])
        if cmd_match:
            command = f'!{cmd_match["cmd"].lstrip("!").lower()}'
            if command in COMMANDS:
                return COMMANDS[command], msg_match

    for pattern, handler in HANDLERS:
        match = pattern.match(msg)
        if match:
            return handler, match

    return None


def _import_plugins() -> None:
    mod_infos = pkgutil.walk_packages(plugins.__path__, f'{plugins.__name__}.')
    for _, name, _ in mod_infos:
        __import__(name, fromlist=['_trash'])


_import_plugins()


@handler('^PING (.*)')
async def pong(config: Config, match: Match[str]) -> str:
    """keeps the bot alive, need to reply with all PINGs with PONG"""
    return f'PONG {match.group(1)}\r\n'


# make this always last so that help is implemented properly
@handle_message(r'!+\w')
async def cmd_help(config: Config, match: Match[str]) -> str:
    possible = [COMMAND_PATTERN_RE.search(reg.pattern) for reg, _ in HANDLERS]
    possible_cmds = {match[0] for match in possible if match}
    possible_cmds.update(COMMANDS)
    possible_cmds.difference_update(SECRET_CMDS)
    commands = ['!help'] + sorted(possible_cmds)

    cmd = match['msg'].split()[0]
    if cmd.startswith(('!help', '!halp')):
        msg = f' possible commands: {", ".join(commands)}'
    else:
        msg = f'unknown command ({esc(cmd)}).'
        suggestions = difflib.get_close_matches(cmd, commands, cutoff=0.7)
        if suggestions:
            msg += f' did you mean: {", ".join(suggestions)}?'
        else:
            msg += f' possible commands: {", ".join(commands)}'
    return format_msg(match, msg)
