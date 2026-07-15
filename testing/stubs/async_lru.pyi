from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

T = TypeVar('T')

def alru_cache(maxsize: int | None) -> Callable[[T], T]: ...
