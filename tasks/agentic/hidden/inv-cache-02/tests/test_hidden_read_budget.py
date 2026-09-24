import builtins
import io

import pytest
from invoicing.lookup import find, find_many
from invoicing.models import Customer, Invoice, LineItem
from invoicing.storage import Store

CUSTOMER = Customer(id="c1", name="Acme")
N = 40


@pytest.fixture
def reads(monkeypatch):
    """Counts every read-mode file open: ``open()`` and everything in ``pathlib`` funnels
    through ``io.open`` (``Path.open`` / ``read_text`` / ``read_bytes``)."""
    counts = {"n": 0}
    real_open = io.open

    def counting_open(file, mode="r", *args, **kwargs):
        if "r" in str(mode):
            counts["n"] += 1
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(io, "open", counting_open)
    monkeypatch.setattr(builtins, "open", counting_open)
    return counts


def _seed(path) -> list[str]:
    store = Store(path)
    ids = [f"i{n}" for n in range(N)]
    for invoice_id in ids:
        store.add(Invoice(id=invoice_id, customer=CUSTOMER, items=[LineItem("W", 1, 1.0)]))
    store.flush()
    return ids


# brief: "resolving any number of ids through one Store, with nothing written in between,
# must read the store file at most once"
def test_batch_lookup_reads_file_at_most_once(tmp_path, reads):
    path = tmp_path / "invoices.json"
    ids = _seed(path)
    reads["n"] = 0
    store = Store(path)
    found = find_many(store, [*ids, "missing-1", "missing-2"])
    assert all(found[i] is not None for i in ids)
    assert found["missing-1"] is None
    assert reads["n"] <= 1


# brief: "every flush must be reflected by the very next read through that store"
def test_read_after_flush_sees_new_invoice(tmp_path, reads):
    path = tmp_path / "invoices.json"
    ids = _seed(path)
    store = Store(path)
    assert find(store, ids[0]) is not None  # warm any cache
    store.add(Invoice(id="fresh", customer=CUSTOMER))
    store.flush()
    assert find(store, "fresh") is not None
    assert len(store.all()) == N + 1


# brief: "an invoice added but not yet flushed must still be found" (storage docstring:
# ``all()`` is on disk plus pending)
def test_pending_invoice_is_found_without_flush(tmp_path, reads):
    path = tmp_path / "invoices.json"
    ids = _seed(path)
    store = Store(path)
    assert find(store, ids[0]) is not None
    store.add(Invoice(id="pending-1", customer=CUSTOMER))
    assert find(store, "pending-1") is not None
    assert len(store.all()) == N + 1


# brief: "after a flush, the next batch of lookups again reads the file at most once"
def test_lookups_after_flush_read_at_most_once(tmp_path, reads):
    path = tmp_path / "invoices.json"
    ids = _seed(path)
    store = Store(path)
    find_many(store, ids)
    store.add(Invoice(id="fresh", customer=CUSTOMER))
    store.flush()
    reads["n"] = 0
    found = find_many(store, [*ids, "fresh"])
    assert found["fresh"] is not None
    assert reads["n"] <= 1


# brief: "a fresh Store opened later on the same path must see everything an earlier one flushed"
def test_fresh_store_sees_earlier_stores_flush(tmp_path, reads):
    path = tmp_path / "invoices.json"
    ids = _seed(path)
    first = Store(path)
    assert find(first, ids[0]) is not None
    first.add(Invoice(id="fresh", customer=CUSTOMER))
    first.flush()
    second = Store(path)
    assert find(second, "fresh") is not None
    assert len(second.all()) == N + 1
