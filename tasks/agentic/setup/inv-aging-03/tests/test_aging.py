from datetime import date

from invoicing.aging import aging, bucket_for, due_date
from invoicing.cli import main
from invoicing.models import Customer, Invoice, LineItem

ACME = Customer(id="c1", name="Acme")


def _inv(inv_id, issued_on, price=100.0, terms=30):
    return Invoice(
        id=inv_id,
        customer=ACME,
        items=[LineItem("W", 1, price)],
        issued_on=issued_on,
        terms_days=terms,
    )


def test_due_date_net_30():
    assert due_date(_inv("i1", "2024-04-01")) == date(2024, 5, 1)


def test_buckets():
    assert bucket_for(0) == "current"
    assert bucket_for(5) == "1-30"
    assert bucket_for(45) == "31-60"
    assert bucket_for(120) == "90+"


def test_aging_report(tmp_path, capsys):
    report = aging([_inv("i1", "2024-03-01"), _inv("i2", "2024-01-01", 50.0)], date(2024, 4, 10))
    assert report["1-30"] == {"count": 1, "amount": 100.0}
    assert report["61-90"] == {"count": 1, "amount": 50.0}

    db = str(tmp_path / "invoices.json")
    main(
        ["--db", db, "create", "--customer", "Acme", "--amount", "80", "--issued-on", "2024-03-01"]
    )
    capsys.readouterr()
    assert main(["--db", db, "aging", "--as-of", "2024-03-20"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "current: 1 invoices, 80.00"
    assert out[-1] == "total: 80.00"
