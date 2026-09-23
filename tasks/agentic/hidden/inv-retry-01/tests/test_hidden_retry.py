from invoicing.models import Customer, Invoice
from invoicing.sync import RateLimited, send_all

CUSTOMER = Customer(id="c1", name="Acme")


def test_retries_and_honors_retry_after(monkeypatch):
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    calls = {"i1": 0}

    def sender(invoice):
        calls[invoice.id] += 1
        if invoice.id == "i1" and calls[invoice.id] == 1:
            raise RateLimited(retry_after=2.5)

    invoices = [Invoice(id="i1", customer=CUSTOMER)]
    result = send_all(invoices, sender)

    assert result == ["i1"]
    assert calls["i1"] == 2
    assert sleeps == [2.5]


def test_gives_up_after_max_retries_and_continues_batch(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    def sender(invoice):
        if invoice.id == "i1":
            raise RateLimited(retry_after=0.1)

    invoices = [Invoice(id="i1", customer=CUSTOMER), Invoice(id="i2", customer=CUSTOMER)]
    result = send_all(invoices, sender, max_retries=3)

    assert "i1" not in result
    assert "i2" in result
