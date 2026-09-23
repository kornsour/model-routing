# invoicing

![Build](https://img.shields.io/badge/build-failing-red)

A small, dependency-free invoicing library and CLI. Invoices are stored as
JSON on disk; the CLI can create invoices, list them, export/import CSV,
sync them to a (simulated) remote billing service, and print a summary
report.

## Layout

- `src/invoicing/models.py` - `Customer`, `LineItem`, `Invoice` dataclasses.
- `src/invoicing/calc.py` - totals, tax, discounts, currency rounding.
- `src/invoicing/query.py` - listing and pagination over stored invoices.
- `src/invoicing/csvio.py` - CSV export/import for invoices.
- `src/invoicing/storage.py` - buffered JSON-file store (`add`, `flush`).
- `src/invoicing/pipeline.py` - builds the end-of-run summary report.
- `src/invoicing/sync.py` - pushes invoices to a (simulated) remote API.
- `src/invoicing/cli.py` - the `invoicing` command-line tool.

## Usage

```
python -m invoicing.cli create --customer "Acme, Inc." --amount 120.00
python -m invoicing.cli list --page 1 --page-size 10
python -m invoicing.cli export-csv invoices.csv
python -m invoicing.cli report
```

## Development

```
python -m pytest -q
```
