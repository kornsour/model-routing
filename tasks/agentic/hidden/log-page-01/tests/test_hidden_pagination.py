import pytest
from logproc.aggregate import paginate
from logproc.parser import LogEntry


def _entries(n):
    return [LogEntry(timestamp=f"t{i}", level="INFO", message=f"m{i}") for i in range(n)]


@pytest.mark.parametrize(("n", "page_size"), [(6, 3), (10, 5), (7, 3), (9, 4)])
def test_paginate_reconstructs_exact_input(n, page_size):
    entries = _entries(n)
    page_count = (n + page_size - 1) // page_size
    seen = []
    for page in range(1, page_count + 1):
        seen.extend(paginate(entries, page=page, page_size=page_size))
    assert seen == entries
