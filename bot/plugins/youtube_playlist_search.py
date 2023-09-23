from __future__ import annotations

from typing import NamedTuple

import aiohttp
import aiosqlite
import async_lru

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.message import Message


class Playlist(NamedTuple):
    name: str
    id: str

    @property
    def url(self) -> str:
        return f'https://www.youtube.com/playlist?list={self.id}'


class YouTubeVideo(NamedTuple):
    playlist: str
    url: str
    title: str

    def chat_message(self) -> str:
        return f'{esc(self.title)} - {esc(self.url)}'


@async_lru.alru_cache(maxsize=None)
async def _info() -> tuple[tuple[Playlist, ...], tuple[YouTubeVideo, ...]]:
    async with aiohttp.ClientSession() as session:
        async with session.get('https://anthonywritescode.github.io/explains/playlists.json') as resp:  # noqa: E501
            resp = await resp.json()

    playlists = tuple(
        Playlist(playlist['playlist_name'], playlist['playlist_id'])
        for playlist in resp['playlists']
    )

    videos = tuple(
        YouTubeVideo(playlist['playlist_name'], **video)
        for playlist in resp['playlists']
        for video in playlist['videos']
    )

    return playlists, videos


@async_lru.alru_cache(maxsize=None)
async def _populate_playlists() -> None:
    async with aiosqlite.connect('db.db') as db:
        await db.execute('DROP TABLE IF EXISTS youtube_videos')
        await db.execute(
            'CREATE VIRTUAL TABLE youtube_videos using FTS5 '
            '(playlist, url, title)',
        )
        await db.commit()

        _, videos = await _info()

        query = 'INSERT INTO youtube_videos VALUES (?, ?, ?)'
        await db.executemany(query, videos)

        await db.commit()


async def _playlist(playlist_name: str) -> Playlist:
    playlists, _ = await _info()
    playlist, = (p for p in playlists if p.name == playlist_name)
    return playlist


async def _search_playlist(
        db: aiosqlite.Connection,
        playlist: str,
        search_terms: str,
) -> list[YouTubeVideo]:
    query = (
        'SELECT playlist, url, title '
        'FROM youtube_videos '
        'WHERE playlist = ? AND title MATCH ? ORDER BY rank'
    )
    # Append a wildcard character to the search to include plurals etc.
    if not search_terms.endswith('*'):
        search_terms += '*'
    async with db.execute(query, (playlist, search_terms)) as cursor:
        results = await cursor.fetchall()
        return [YouTubeVideo(*row) for row in results]


async def _msg(playlist_name: str, search_terms: str) -> str:
    await _populate_playlists()

    playlist = await _playlist(playlist_name)

    if not search_terms.strip():
        return f'see playlist: {playlist.url}'

    async with aiosqlite.connect('db.db') as db:
        try:
            videos = await _search_playlist(db, playlist_name, search_terms)
        except aiosqlite.OperationalError:
            return 'invalid search syntax used'

        if not videos:
            return f'no video found - see playlist: {playlist.url}'
        elif len(videos) > 2:
            return (
                f'{videos[0].chat_message()} and {len(videos)} other '
                f'videos found - see playlist: {playlist.url}'
            )
        elif len(videos) == 2:
            return (
                '2 videos found: '
                f'{videos[0].chat_message()} & {videos[1].chat_message()}'
            )
        else:
            return videos[0].chat_message()


@command('!explain', '!explains')
async def cmd_explain(config: Config, msg: Message) -> str:
    _, _, rest = msg.msg.partition(' ')
    return format_msg(msg, await _msg('explains', rest))


@command('!faq')
async def cmd_faq(config: Config, msg: Message) -> str:
    _, _, rest = msg.msg.partition(' ')
    return format_msg(msg, await _msg('faq', rest))
