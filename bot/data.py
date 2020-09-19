import pkgutil
import re
from typing import Callable
from typing import Dict
from typing import List
from typing import Match
from typing import Optional
from typing import Pattern
from typing import Set
from typing import Tuple

from bot import plugins
from bot.config import Config
from bot.permissions import parse_badge_info

# TODO: maybe move this?
PRIVMSG = 'PRIVMSG #{channel} : {msg}\r\n'
COMMAND_PATTERN_RE = re.compile(r'!\w+')
MSG_RE = re.compile(
    '^@(?P<info>[^ ]+) :(?P<user>[^!]+).* '
    'PRIVMSG #(?P<channel>[^ ]+) '
    ':(?P<msg>[^\r]+)',
)
COMMAND_RE = re.compile(r'^(?P<cmd>!\w+)')


def get_fake_msg(config: Config, msg: str) -> str:
    info = '@color=;display-name=username;badges='
    return f'{info} :username PRIVMSG #{config.channel} :{msg}\r\n'


# TODO: move this and/or delete this
def esc(s: str) -> str:
    return s.replace('{', '{{').replace('}', '}}')


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
PERIODIC_HANDLERS: List[Tuple[int, Callback]] = []


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


def periodic_handler(*, minutes: int) -> Callable[[Callback], Callback]:
    def periodic_handler_decorator(func: Callback) -> Callback:
        PERIODIC_HANDLERS.append((minutes, func))
        return func
    return periodic_handler_decorator


def get_handler(msg: str) -> Optional[Tuple[Callback, Match[str]]]:
    msg_match = MSG_RE.match(msg)
    if msg_match:
        info = parse_badge_info(msg_match['info'])

        if 'custom-reward-id' in info:
            if info['custom-reward-id'] in POINTS_HANDLERS:
                return POINTS_HANDLERS[info['custom-reward-id']], msg_match
            else:
                return None

        cmd_match = COMMAND_RE.match(msg_match['msg'])
        if cmd_match and cmd_match['cmd'].lower() in COMMANDS:
            return COMMANDS[cmd_match['cmd'].lower()], msg_match

    for pattern, handler in HANDLERS:
        match = pattern.match(msg)
        if match:
            return handler, match

    return None


# trigger an import of all of the plugins
# https://github.com/python/mypy/issues/1422
plugins_path: str = plugins.__path__  # type: ignore
mod_infos = pkgutil.walk_packages(plugins_path, f'{plugins.__name__}.')
for _, name, _ in mod_infos:
    __import__(name, fromlist=['_trash'])


@handler('^PING (.*)')
def pong(match: Match[str]) -> Response:
    """keeps the bot alive, need to reply with all PINGs with PONG"""
    return CmdResponse(f'PONG {match.group(1)}\r\n')


# make this always last so that help is implemented properly
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
