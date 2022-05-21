from __future__ import annotations

import functools
import os.path

import aiohttp

from bot.util import atomic_open

CACHE = '.cache'


@functools.lru_cache(maxsize=1)
def _ensure_cache_gitignore() -> None:
    gitignore_path = os.path.join(CACHE, '.gitignore')
    if os.path.exists(gitignore_path):
        return
    with atomic_open(gitignore_path) as f:
        f.write(b'*\n')


def local_image_path(subtype: str, name: str) -> str:
    return os.path.join(CACHE, subtype, f'{name}.png')


async def download(subtype: str, name: str, url: str) -> None:
    img_path = local_image_path(subtype, name)
    if os.path.exists(img_path):
        return

    img_dir = os.path.join(CACHE, subtype)
    os.makedirs(img_dir, exist_ok=True)

    _ensure_cache_gitignore()

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()

    with atomic_open(img_path) as f:
        f.write(data)
