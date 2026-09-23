from invoicing.cli import main
from invoicing.fx import to_usd


class FixedRates:
    def __init__(self, table):
        self.table = table

    def rate(self, currency):
        return self.table[currency]


def test_to_usd_converts_and_rounds():
    assert to_usd(100.0, "EUR", FixedRates({"EUR": 1.08})) == 108.0


def test_report_usd_lines(tmp_path, capsys):
    db = str(tmp_path / "invoices.json")
    main(["--db", db, "create", "--customer", "Acme", "--amount", "100", "--currency", "eur"])
    main(["--db", db, "create", "--customer", "Globex", "--amount", "50"])
    capsys.readouterr()
    rates = FixedRates({"EUR": 1.10, "USD": 1.0})
    assert main(["--db", db, "report", "--usd"], rates=rates) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [
        "2 invoices, total 150.00",
        "total in USD: 160.00",
        "  Acme: 110.00 USD",
        "  Globex: 50.00 USD",
    ]
