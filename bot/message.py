from __future__ import annotations

import re
from typing import NamedTuple

MSG_RE = re.compile(
    '^@(?P<info>[^ ]+) :(?P<user>[^!]+).* '
    'PRIVMSG #(?P<channel>[^ ]+) '
    ':(?P<msg>[^\r]+)',
)


class Message(NamedTuple):
    msg: str
    channel: str
    info: dict[str, str]

    @property
    def badges(self) -> tuple[str, ...]:
        return tuple(self.info['badges'].split(','))

    @property
    def display_name(self) -> str:
        return self.info['display-name']

    @property
    def name_key(self) -> str:
        """compat with old match['msg']"""
        return self.display_name.lower()

    @property
    def optional_user_arg(self) -> str:
        _, _, rest = self.msg.strip().partition(' ')
        if rest:
            return rest.lstrip('@')
        else:
            return self.display_name

    @property
    def is_moderator(self) -> bool:
        return any(badge.startswith('moderator/') for badge in self.badges)

    @property
    def is_subscriber(self) -> bool:
        possible = ('founder/', 'subscriber/')
        return any(badge.startswith(possible) for badge in self.badges)

    @classmethod
    def parse(cls, msg: str) -> Message | None:
        match = MSG_RE.match(msg)
        if match is not None:
            info = {}
            for part in match['info'].split(';'):
                k, v = part.split('=', 1)
                info[k] = v
            return cls(match['msg'], match['channel'], info)
        else:
            return None
