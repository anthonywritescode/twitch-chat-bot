from __future__ import annotations

import contextlib
import os.path
import tempfile
from typing import Generator
from typing import IO


def get_quantified_unit(unit: str, amount: int) -> str:
    if amount == 1:
        return unit
    else:
        return f'{unit}s'


def seconds_to_readable(seconds: int) -> str:
    parts = []
    for n, unit in (
            (60 * 60, 'hour'),
            (60, 'minute'),
            (1, 'second'),
    ):
        if seconds // n:
            unit = get_quantified_unit(unit, seconds // n)
            parts.append(f'{seconds // n} {unit}')
        seconds %= n
    return ', '.join(parts)


@contextlib.contextmanager
def atomic_open(filename: str) -> Generator[IO[bytes], None, None]:
    fd, fname = tempfile.mkstemp(dir=os.path.dirname(filename))
    try:
        with open(fd, 'wb') as f:
            yield f
        os.replace(fname, filename)
    except BaseException:
        os.remove(fname)
        raise
