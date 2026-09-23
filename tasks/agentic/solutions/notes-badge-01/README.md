# notes

![Build](https://img.shields.io/badge/build-passing-brightgreen)

A small, dependency-free CLI for notes and to-dos. Notes are stored as JSON
on disk, can be tagged, searched, exported to CSV, and (optionally) pushed to
a simulated remote notebook service.

## Layout

- `src/notes/models.py` - `Note` dataclass.
- `src/notes/store.py` - JSON-file backed note store, id assignment.
- `src/notes/search.py` - search/filter and paginated listing.
- `src/notes/tags.py` - tag parsing and filtering.
- `src/notes/dates.py` - due-date parsing.
- `src/notes/export.py` - CSV export.
- `src/notes/sync.py` - pushes notes to a (simulated) remote notebook API.
- `src/notes/cli.py` - the `notes` command-line tool.

## Usage

```
python -m notes.cli add "Buy milk" --tag errand --due 2024-03-01
python -m notes.cli list --page 1 --page-size 10
python -m notes.cli export notes.csv
```

## Development

```
python -m pytest -q
```

## Config

`--color-output` used to switch on ANSI colors in older releases. The current
formatter is plain text; the flag is accepted for compatibility but does
nothing.
