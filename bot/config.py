from __future__ import annotations

from typing import NamedTuple


class Config(NamedTuple):
    username: str
    channel: str
    oauth_token: str
    client_id: str
    youtube_api_key: str
    youtube_playlists: dict[str, dict[str, str]]
    airnow_api_key: str

    @property
    def oauth_token_token(self) -> str:
        _, token = self.oauth_token.split(':', 1)
        return token

    def __repr__(self) -> str:
        return (
            f'{type(self).__name__}('
            f'username={self.username!r}, '
            f'channel={self.channel!r}, '
            f'oauth_token={"***"!r}, '
            f'client_id={"***"!r}, '
            f'youtube_api_key={"***"!r}, '
            f'youtube_playlists={self.youtube_playlists!r}, '
            f'airnow_api_key={"***"!r}, '
            f')'
        )
