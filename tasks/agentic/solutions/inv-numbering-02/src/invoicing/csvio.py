"""Export/import invoices as a flat CSV (one row per line item).

Columns: invoice_id, customer_name, description, quantity, unit_price.

On import, rows sharing a non-blank ``invoice_id`` form one invoice; a row
with a blank ``invoice_id`` is an invoice of its own with an empty id, which
the caller must number (see ``invoicing.numbering``) before storing it.
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

    invoices: list[Invoice] = []
    by_id: dict[str, Invoice] = {}
    for row in rows[1:]:
        invoice_id, customer_name, description, quantity, unit_price = row.split(",")
        invoice_id = invoice_id.strip()
        item = LineItem(
            description=description, quantity=int(quantity), unit_price=float(unit_price)
        )
        if invoice_id and invoice_id in by_id:
            by_id[invoice_id].items.append(item)
            continue
        invoice = Invoice(
            id=invoice_id,
            customer=Customer(id=customer_name, name=customer_name),
            items=[item],
        )
        invoices.append(invoice)
        if invoice_id:
            by_id[invoice_id] = invoice
    return invoices
