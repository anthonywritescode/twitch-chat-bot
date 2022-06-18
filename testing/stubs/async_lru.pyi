from typing import Callable, TypeVar

T = TypeVar('T')

def alru_cache(maxsize: int | None) -> Callable[[T], T]: ...
