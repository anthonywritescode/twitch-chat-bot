from typing import List
from typing import Match
from typing import NamedTuple
from typing import Optional

import aiohttp
import aiosqlite
import async_lru

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import MessageResponse


class YouTubeVideo(NamedTuple):
    video_id: str
    title: str
    playlist_id: str

    def chat_message(self) -> str:
        return (
            f'{esc(self.title)} - '
            f'https://youtu.be/{self.video_id}?list={self.playlist_id}'
        )


async def _fetch_playlist(
        playlist_id: str,
        *,
        api_key: str,
) -> List[YouTubeVideo]:
    url = 'https://www.googleapis.com/youtube/v3/playlistItems'
    params = {
        'part': 'snippet',
        'playlistId': playlist_id,
        'key': api_key,
        'maxResults': 50,
    }
    playlist_videos = []
    more_pages = True
    async with aiohttp.ClientSession() as session:
        while more_pages:
            async with session.get(url, params=params) as resp:
                json_resp = await resp.json()
                playlist_videos.extend(json_resp['items'])
                next_page_token = json_resp.get('nextPageToken')
                if next_page_token:
                    params['pageToken'] = next_page_token
                else:
                    more_pages = False

        return [
            YouTubeVideo(
                video_id=v['snippet']['resourceId']['videoId'],
                title=v['snippet']['title'],
                playlist_id=v['snippet']['playlistId'],
            )
            for v in playlist_videos
        ]


@async_lru.alru_cache(maxsize=None)
async def _populate_playlist(playlist_id: str, *, api_key: str) -> None:
    async with aiosqlite.connect('db.db') as db:
        await db.execute(
            'CREATE VIRTUAL TABLE IF NOT EXISTS youtube_videos using FTS5 ('
            '   video_id,'
            '   title,'
            '   playlist_id'
            ')',
        )
        await db.commit()

        videos = await _fetch_playlist(playlist_id, api_key=api_key)

        query = 'DELETE FROM youtube_videos WHERE playlist_id = ?'
        await db.execute(query, (playlist_id,))

        query = 'INSERT INTO youtube_videos VALUES (?, ?, ?)'
        await db.executemany(query, videos)

        await db.commit()


async def _search_playlist(
        db: aiosqlite.Connection,
        playlist_id: str,
        search_terms: str
) -> List[YouTubeVideo]:
    query = (
        'SELECT video_id, title, playlist_id '
        'FROM youtube_videos '
        'WHERE playlist_id = ? AND title MATCH ? ORDER BY rank'
    )
    # Append a wildcard character to the search to include plurals etc.
    if not search_terms.endswith('*'):
        search_terms += '*'
    async with db.execute(query, (playlist_id, search_terms)) as cursor:
        results = await cursor.fetchall()
        return [YouTubeVideo(*row) for row in results]


class PlaylistVideoResponse(MessageResponse):
    def __init__(
            self,
            match: Match[str],
            playlist_name: str,
            search_terms: str,
    ) -> None:
        self.playlist_name = playlist_name
        self.search_terms = search_terms
        super().__init__(match, '')

    async def __call__(self, config: Config) -> Optional[str]:
        info = config.youtube_playlists[self.playlist_name]
        playlist_id = info['playlist_id']
        playlist_url = f'https://www.youtube.com/playlist?list={playlist_id}'
        if not self.search_terms:
            self.msg_fmt = f'playlist: {playlist_url}'
            if info.get('github'):
                self.msg_fmt = f'{self.msg_fmt} video list: {info["github"]}'
            return await super().__call__(config)

        await _populate_playlist(playlist_id, api_key=config.youtube_api_key)

        async with aiosqlite.connect('db.db') as db:
            try:
                videos = await _search_playlist(
                    db, playlist_id, self.search_terms,
                )
            except aiosqlite.OperationalError:
                self.msg_fmt = 'invalid search syntax used'
                return await super().__call__(config)

            if not videos:
                self.msg_fmt = f'no video found - see playlist: {playlist_url}'
            elif len(videos) > 2:
                self.msg_fmt = (
                    f'{videos[0].chat_message()} and {len(videos)} other '
                    f'videos found - see playlist: {playlist_url}'
                )
            elif len(videos) == 2:
                self.msg_fmt = (
                    '2 videos found: '
                    f'{videos[0].chat_message()} & {videos[1].chat_message()}'
                )
            else:
                self.msg_fmt = videos[0].chat_message()

        return await super().__call__(config)


@command('!explain', '!explain')
def cmd_explain(match: Match[str]) -> PlaylistVideoResponse:
    _, _, rest = match['msg'].partition(' ')
    return PlaylistVideoResponse(match, 'explains', rest)


@command('!faq')
def cmd_faq(match: Match[str]) -> PlaylistVideoResponse:
    _, _, rest = match['msg'].partition(' ')
    return PlaylistVideoResponse(match, 'faq', rest)
