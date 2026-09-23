"""Export/import invoices as a flat CSV (one row per line item).

Columns: invoice_id, customer_name, description, quantity, unit_price.
"""

from __future__ import annotations

from pathlib import Path

from invoicing.models import Customer, Invoice, LineItem

HEADER = "invoice_id,customer_name,description,quantity,unit_price"


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
            ]
            lines.append(",".join(fields))
    Path(path).write_text("\n".join(lines) + "\n")


def import_csv(path: str | Path) -> list[Invoice]:
    text = Path(path).read_text()
    rows = [line for line in text.splitlines() if line.strip()]
    if not rows or rows[0] != HEADER:
        raise ValueError("missing or unexpected CSV header")

    by_id: dict[str, Invoice] = {}
    for row in rows[1:]:
        invoice_id, customer_name, description, quantity, unit_price = row.split(",")
        if invoice_id not in by_id:
            by_id[invoice_id] = Invoice(
                id=invoice_id,
                customer=Customer(id=customer_name, name=customer_name),
            )
        by_id[invoice_id].items.append(
            LineItem(
                description=description,
                quantity=int(quantity),
                unit_price=float(unit_price),
            )
        )
    return list(by_id.values())
