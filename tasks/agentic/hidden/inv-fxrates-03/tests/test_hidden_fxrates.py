from collections import Counter

from invoicing.cli import main
from invoicing.models import Customer, Invoice, LineItem
from invoicing.pipeline import generate_summary
from invoicing.statement import customer_balances
from invoicing.storage import Store


class CountingRates:
    """A fake rate service that records every request it receives."""

    def __init__(self, table):
        self.table = dict(table)
        self.calls: Counter[str] = Counter()

    def rate(self, currency):
        self.calls[currency] += 1
        return self.table[currency]


ACME = Customer(id="c1", name="Acme")
GLOBEX = Customer(id="c2", name="Globex")


def _seed(path):
    store = Store(path)
    rows = [
        ("i1", ACME, 100.0, "EUR"),
        ("i2", GLOBEX, 200.0, "EUR"),
        ("i3", ACME, 10.0, "GBP"),
        ("i4", GLOBEX, 50.0, "USD"),
        ("i5", ACME, 300.0, "EUR"),
        ("i6", GLOBEX, 20.0, "GBP"),
        ("i7", ACME, 5.0, "USD"),
    ]
    for inv_id, cust, price, cur in rows:
        store.add(Invoice(id=inv_id, customer=cust, items=[LineItem("W", 1, price)], currency=cur))
    store.flush()
    return store


RATES = {"EUR": 1.10, "GBP": 1.25, "USD": 1.0}


def _report(db, rates, capsys):
    capsys.readouterr()
    assert main(["--db", db, "report", "--usd"], rates=rates) == 0
    return capsys.readouterr().out.splitlines()


# brief: "one `report --usd` run must ask the rate service at most once per currency it needs,
# however many invoices use it, and never for USD amounts"; figures must not change
def test_report_run_asks_once_per_currency(tmp_path, capsys):
    db = str(tmp_path / "invoices.json")
    _seed(db)
    rates = CountingRates(RATES)
    out = _report(db, rates, capsys)
    assert out == [
        "7 invoices, total 685.00",
        "total in USD: 752.50",
        "  Acme: 457.50 USD",
        "  Globex: 295.00 USD",
    ]
    assert rates.calls == Counter({"EUR": 1, "GBP": 1})


# brief: "rates move daily, so every run must ask the service afresh - nothing may be reused
# from an earlier run, even one in the same process with the same service object"
def test_each_run_asks_again_and_sees_new_rates(tmp_path, capsys):
    db = str(tmp_path / "invoices.json")
    _seed(db)
    rates = CountingRates(RATES)
    _report(db, rates, capsys)
    rates.table["EUR"] = 1.20
    rates.calls.clear()
    out = _report(db, rates, capsys)
    assert out[1] == "total in USD: 812.50"
    assert rates.calls == Counter({"EUR": 1, "GBP": 1})


# brief: "the same budget holds for `generate_summary` and `customer_balances` called on their
# own" (and they must not reuse rates across calls either)
def test_library_functions_keep_the_budget(tmp_path):
    store = _seed(tmp_path / "invoices.json")
    rates = CountingRates(RATES)
    assert generate_summary(store, rates)["total_usd"] == 752.5
    assert rates.calls == Counter({"EUR": 1, "GBP": 1})

    rates.calls.clear()
    assert customer_balances(store.all(), rates) == {"Acme": 457.5, "Globex": 295.0}
    assert rates.calls == Counter({"EUR": 1, "GBP": 1})

    rates.table["GBP"] = 2.0
    rates.calls.clear()
    assert generate_summary(store, rates)["total_usd"] == 775.0
    assert rates.calls == Counter({"EUR": 1, "GBP": 1})


# brief: "USD amounts ... never" reach the service - an all-USD store makes no calls at all
def test_all_usd_store_makes_no_calls(tmp_path, capsys):
    db = str(tmp_path / "invoices.json")
    store = Store(db)
    store.add(Invoice(id="u1", customer=ACME, items=[LineItem("W", 3, 10.0)]))
    store.flush()
    rates = CountingRates({})
    out = _report(db, rates, capsys)
    assert out[1] == "total in USD: 30.00"
    assert sum(rates.calls.values()) == 0
