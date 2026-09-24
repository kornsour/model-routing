"""Export/import invoices as a flat CSV (one row per line item).

Columns: invoice_id, customer_name, description, quantity, unit_price, currency.
Files exported before the currency column existed (five columns) still import,
as USD.
"""

from __future__ import annotations

from pathlib import Path

from invoicing.models import DEFAULT_CURRENCY, Customer, Invoice, LineItem

LEGACY_HEADER = "invoice_id,customer_name,description,quantity,unit_price"
HEADER = LEGACY_HEADER + ",currency"


def export_csv(invoices: list[Invoice], path: str | Path) -> None:
    lines = [HEADER]
    for inv in invoices:
        for item in inv.items:
            fields = [
                inv.id,
                inv.customer.name,
                item.description,
                str(item.quantity),
                str(item.unit_price),
                inv.currency,
            ]
            lines.append(",".join(fields))
    Path(path).write_text("\n".join(lines) + "\n")


def import_csv(path: str | Path) -> list[Invoice]:
    text = Path(path).read_text()
    rows = [line for line in text.splitlines() if line.strip()]
    if not rows or rows[0] not in (HEADER, LEGACY_HEADER):
        raise ValueError("missing or unexpected CSV header")
    has_currency = rows[0] == HEADER

    by_id: dict[str, Invoice] = {}
    for row in rows[1:]:
        fields = row.split(",")
        invoice_id, customer_name, description, quantity, unit_price = fields[:5]
        currency = fields[5] if has_currency else DEFAULT_CURRENCY
        if invoice_id not in by_id:
            by_id[invoice_id] = Invoice(
                id=invoice_id,
                customer=Customer(id=customer_name, name=customer_name),
                currency=currency,
            )
        by_id[invoice_id].items.append(
            LineItem(
                description=description,
                quantity=int(quantity),
                unit_price=float(unit_price),
            )
        )
    return list(by_id.values())
