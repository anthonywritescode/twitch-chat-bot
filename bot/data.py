from __future__ import annotations

import difflib
import pkgutil
import re
from typing import Awaitable
from typing import Callable
from typing import Optional
from typing import Pattern

from bot import plugins
from bot.config import Config
from bot.message import Message

# TODO: maybe move this?
PRIVMSG = 'PRIVMSG #{channel} : {msg}\r\n'
COMMAND_RE = re.compile(r'^(?P<cmd>!+[a-zA-Z0-9-]+)')


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


def format_msg(msg: Message, fmt: str) -> str:
    params = {'user': msg.display_name, 'channel': msg.channel}
    params['msg'] = fmt.format(**params)
    return PRIVMSG.format(**params)


Callback = Callable[[Config, Message], Awaitable[Optional[str]]]
MSG_HANDLERS: list[tuple[Pattern[str], Callback]] = []
COMMANDS: dict[str, Callback] = {}
POINTS_HANDLERS: dict[str, Callback] = {}
BITS_HANDLERS: dict[int, Callback] = {}
SECRET_CMDS: set[str] = set()
PERIODIC_HANDLERS: list[tuple[int, Callback]] = []


def handle_message(
        *message_prefixes: str,
        flags: re.RegexFlag = re.U,
) -> Callable[[Callback], Callback]:
    def handle_message_decorator(func: Callback) -> Callback:
        for prefix in message_prefixes:
            MSG_HANDLERS.append((re.compile(prefix, flags=flags), func))

        return func
    return handle_message_decorator


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


def get_handler(msg: str) -> tuple[Callback, Message] | None:
    parsed = Message.parse(msg)
    if parsed:
        if 'custom-reward-id' in parsed.info:
            if parsed.info['custom-reward-id'] in POINTS_HANDLERS:
                return POINTS_HANDLERS[parsed.info['custom-reward-id']], parsed
            else:
                return None

        if 'bits' in parsed.info:
            bits_n = int(parsed.info['bits'])
            if bits_n % 100 in BITS_HANDLERS:
                return BITS_HANDLERS[bits_n % 100], parsed

        cmd_match = COMMAND_RE.match(parsed.msg)
        if cmd_match:
            command = f'!{cmd_match["cmd"].lstrip("!").lower()}'
            if command in COMMANDS:
                return COMMANDS[command], parsed

        for pattern, handler in MSG_HANDLERS:
            match = pattern.match(parsed.msg)
            if match:
                return handler, parsed

    return None


def _import_plugins() -> None:
    mod_infos = pkgutil.walk_packages(plugins.__path__, f'{plugins.__name__}.')
    for _, name, _ in mod_infos:
        __import__(name, fromlist=['_trash'])


_import_plugins()


# make this always last so that help is implemented properly
@handle_message(r'!+\w')
async def cmd_help(config: Config, msg: Message) -> str:
    possible_cmds = COMMANDS.keys() - SECRET_CMDS
    possible_cmds.difference_update(SECRET_CMDS)
    commands = ['!help'] + sorted(possible_cmds)

    cmd = msg.msg.split()[0]
    if cmd.startswith(('!help', '!halp')):
        msg_s = f' possible commands: {", ".join(commands)}'
    else:
        msg_s = f'unknown command ({esc(cmd)}).'
        suggestions = difflib.get_close_matches(cmd, commands, cutoff=0.7)
        if suggestions:
            msg_s += f' did you mean: {", ".join(suggestions)}?'
        else:
            msg_s += f' possible commands: {", ".join(commands)}'
    return format_msg(msg, msg_s)
