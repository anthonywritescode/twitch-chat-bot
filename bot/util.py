import contextlib
import os.path
import tempfile
from typing import Generator
from typing import IO


def seconds_to_readable(seconds: int) -> str:
    parts = []
    for n, unit in (
            (60 * 60, 'hours'),
            (60, 'minutes'),
            (1, 'seconds'),
    ):
        if seconds // n:
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
