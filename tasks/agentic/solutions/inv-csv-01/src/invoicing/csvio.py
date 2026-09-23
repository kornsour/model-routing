"""Export/import invoices as a flat CSV (one row per line item).

Columns: invoice_id, customer_name, description, quantity, unit_price.
"""

from __future__ import annotations

import csv
from pathlib import Path

from invoicing.models import Customer, Invoice, LineItem

HEADER = ["invoice_id", "customer_name", "description", "quantity", "unit_price"]


def export_csv(invoices: list[Invoice], path: str | Path) -> None:
    with Path(path).open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for inv in invoices:
            for item in inv.items:
                writer.writerow(
                    [
                        inv.id,
                        inv.customer.name,
                        item.description,
                        item.quantity,
                        item.unit_price,
                    ]
                )


def import_csv(path: str | Path) -> list[Invoice]:
    with Path(path).open(newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            header = []
        if header != HEADER:
            raise ValueError("missing or unexpected CSV header")

        by_id: dict[str, Invoice] = {}
        for row in reader:
            if not row:
                continue
            invoice_id, customer_name, description, quantity, unit_price = row
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
