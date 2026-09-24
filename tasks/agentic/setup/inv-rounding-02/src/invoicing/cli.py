"""Command-line entry point for the invoicing tool."""

from __future__ import annotations

import argparse
import sys
import uuid

from invoicing.calc import total
from invoicing.csvio import export_csv, import_csv
from invoicing.models import Customer, Invoice, LineItem
from invoicing.pipeline import generate_summary
from invoicing.query import paginate
from invoicing.statement import statement_for
from invoicing.storage import Store

DEFAULT_DB = "invoices.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="invoicing")
    parser.add_argument("--db", default=DEFAULT_DB, help="path to the JSON invoice store")
    parser.add_argument(
        "--legacy-tax-table",
        action="store_true",
        help="use the pre-2023 flat tax table instead of per-item tax_rate",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="create a new invoice")
    create.add_argument("--customer", required=True)
    create.add_argument("--description", default="Services rendered")
    create.add_argument("--quantity", type=int, default=1)
    create.add_argument("--amount", type=float, required=True, help="unit price")
    create.add_argument("--tax-rate", type=float, default=0.0)

    listp = sub.add_parser("list", help="list invoices, paginated")
    listp.add_argument("--page", type=int, default=1)
    listp.add_argument("--page-size", type=int, default=10)

    export = sub.add_parser("export-csv", help="export all invoices to CSV")
    export.add_argument("path")

    imp = sub.add_parser("import-csv", help="import invoices from CSV")
    imp.add_argument("path")

    sub.add_parser("report", help="print a summary of all invoices")

    statement = sub.add_parser("statement", help="print one customer's lines and balance")
    statement.add_argument("--customer", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    store = Store(args.db)

    if args.command == "create":
        customer = Customer(id=str(uuid.uuid4())[:8], name=args.customer)
        item = LineItem(
            description=args.description, quantity=args.quantity, unit_price=args.amount
        )
        invoice = Invoice(
            id=str(uuid.uuid4())[:8],
            customer=customer,
            items=[item],
            tax_rate=args.tax_rate,
        )
        store.add(invoice)
        store.flush()
        print(f"created invoice {invoice.id} for {format(total(invoice), '.2f')}")
        return 0

    if args.command == "list":
        invoices = store.all()
        for invoice in paginate(invoices, args.page, args.page_size):
            print(f"{invoice.id}\t{invoice.customer.name}\t{total(invoice):.2f}")
        return 0

    if args.command == "export-csv":
        export_csv(store.all(), args.path)
        print(f"exported {len(store.all())} invoices to {args.path}")
        return 0

    if args.command == "import-csv":
        imported = import_csv(args.path)
        for invoice in imported:
            store.add(invoice)
        store.flush()
        print(f"imported {len(imported)} invoices from {args.path}")
        return 0

    if args.command == "statement":
        result = statement_for(store.all(), args.customer)
        for invoice_id, description, amount in result["lines"]:
            print(f"{invoice_id}\t{description}\t{amount:.2f}")
        print(f"balance {result['balance']:.2f}")
        return 0

    if args.command == "report":
        summary = generate_summary(store)
        print(f"{summary['count']} invoices, total {summary['total']:.2f}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
