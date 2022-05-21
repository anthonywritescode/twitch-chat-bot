from __future__ import annotations

from typing import NamedTuple


class EmotePosition(NamedTuple):
    start: int
    end: int
    emote: str

    @property
    def download_url(self) -> str:
        return f'https://static-cdn.jtvnw.net/emoticons/v2/{self.emote}/default/dark/2.0'  # noqa: E501


def parse_emote_info(s: str) -> list[EmotePosition]:
    if not s:
        return []

    ret = []
    for part in s.split('/'):
        emote, _, positions = part.partition(':')
        for pos in positions.split(','):
            start_s, _, end_s = pos.partition('-')
            ret.append(EmotePosition(int(start_s), int(end_s), emote))
    ret.sort()
    return ret
