from __future__ import annotations

import itertools
from collections.abc import Iterator
from collections.abc import Sequence


def tied_rank(
        counts: Sequence[tuple[str, int]],
) -> Iterator[tuple[int, tuple[int, Iterator[tuple[str, int]]]]]:
    # "counts" should be sorted, usually produced by Counter.most_common()
    grouped = itertools.groupby(counts, key=lambda pair: pair[1])
    yield from enumerate(grouped, start=1)
