import json

import pytest
from invoicing.models import Customer, Invoice, LineItem
from invoicing.storage import Store
from invoicing.sync import RateLimited, sync_store

CUSTOMER = Customer(id="c1", name="Acme")


def _store(path, n=5):
    store = Store(path)
    for i in range(1, n + 1):
        store.add(Invoice(id=f"i{i}", customer=CUSTOMER, items=[LineItem("W", i, 10.0)]))
    store.flush()
    return store


class Remote:
    """Counts every call; fails on the ``fail_on``-th call of this run only."""

    def __init__(self, fail_on=None, exc=None):
        self.received: list[str] = []
        self.calls = 0
        self.fail_on = fail_on
        self.exc = exc

    def __call__(self, invoice):
        self.calls += 1
        if self.calls == self.fail_on:
            raise self.exc
        self.received.append(invoice.id)


# brief: "an unchanged invoice the remote already accepted must never be sent again"
def test_second_run_sends_nothing(tmp_path):
    store = _store(tmp_path / "invoices.json")
    ledger = tmp_path / "ledger.json"
    first, second = Remote(), Remote()
    assert sync_store(store, first, ledger) == ["i1", "i2", "i3", "i4", "i5"]
    assert sync_store(store, second, ledger) == []
    assert second.calls == 0


# brief: "when the remote rate-limits, the run stops without raising and reports the ids it
# did send; the next run picks up the rest, so every invoice reaches the remote exactly once"
def test_rate_limit_stops_cleanly_and_next_run_resumes(tmp_path):
    store = _store(tmp_path / "invoices.json")
    ledger = tmp_path / "ledger.json"
    first = Remote(fail_on=3, exc=RateLimited(1.0))
    assert sync_store(store, first, ledger) == ["i1", "i2"]
    second = Remote()
    assert sync_store(store, second, ledger) == ["i3", "i4", "i5"]
    assert first.received + second.received == ["i1", "i2", "i3", "i4", "i5"]
    assert second.calls == 3


# brief: "if a run dies partway for any other reason, the error still surfaces, but
# invoices the remote accepted before it died must not be sent again next run"
def test_crash_mid_run_keeps_progress(tmp_path):
    store = _store(tmp_path / "invoices.json")
    ledger = tmp_path / "ledger.json"
    first = Remote(fail_on=4, exc=ConnectionError("connection reset"))
    with pytest.raises(ConnectionError):
        sync_store(store, first, ledger)
    second = Remote()
    assert sync_store(store, second, ledger) == ["i4", "i5"]
    assert second.calls == 2


# brief: "an invoice the remote did not accept must be sent on the next run"
def test_rejected_invoice_is_retried_next_run(tmp_path):
    store = _store(tmp_path / "invoices.json", n=2)
    ledger = tmp_path / "ledger.json"
    with pytest.raises(ConnectionError):
        sync_store(store, Remote(fail_on=1, exc=ConnectionError("down")), ledger)
    second = Remote()
    assert sync_store(store, second, ledger) == ["i1", "i2"]


# brief: "an invoice that changed after the remote accepted it (status, line items, anything
# the remote stores) must be sent again - once - and unchanged invoices must not"
def test_changed_invoice_is_resent_once(tmp_path):
    path = tmp_path / "invoices.json"
    store = _store(path, n=3)
    ledger = tmp_path / "ledger.json"
    sync_store(store, Remote(), ledger)

    edited = Store(path)
    invoices = edited.all()
    invoices[1].status = "paid"
    invoices[2].items.append(LineItem("Extra", 1, 1.0))
    edited.path.write_text(json.dumps([inv.to_dict() for inv in invoices], indent=2))

    second = Remote()
    assert sync_store(Store(path), second, ledger) == ["i2", "i3"]
    third = Remote()
    assert sync_store(Store(path), third, ledger) == []
    assert third.calls == 0


# brief: "ledger files written by the current version must keep working: upgrading must not
# resend invoices they already record"
def test_existing_ledger_format_still_honoured(tmp_path):
    store = _store(tmp_path / "invoices.json", n=3)
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps(["i1", "i2"]))
    remote = Remote()
    assert sync_store(store, remote, ledger) == ["i3"]
    assert remote.calls == 1
    again = Remote()
    assert sync_store(store, again, ledger) == []
