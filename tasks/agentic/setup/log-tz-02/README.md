# logproc

![Build](https://img.shields.io/badge/build-failing-red)

A small, dependency-free package for parsing app log lines, aggregating them
into per-level counts, exporting to CSV, and pushing a batch summary to a
(simulated) remote metrics endpoint.

## Layout

- `src/logproc/parser.py` - parses `"TIMESTAMP LEVEL message"` log lines.
- `src/logproc/aggregate.py` - counts entries by level; pagination over them.
- `src/logproc/csvexport.py` - CSV export of parsed entries.
- `src/logproc/timestamps.py` - timestamp parsing shared by the report and the window filter.
- `src/logproc/window.py` - `--since` / `--until` filtering of entries.
- `src/logproc/pipeline.py` - reads a log file, writes entries, builds a report.
- `src/logproc/retry.py` - retry-with-backoff helper for the remote push.
- `src/logproc/cli.py` - the `logproc` command-line tool.

## Usage

```
python -m logproc.cli process app.log --out entries.csv
python -m logproc.cli report entries.csv
python -m logproc.cli report entries.csv --since 2024-03-01T10:00:00Z --until 2024-03-01T11:00:00Z
```

## Timestamps

Every service writes the timestamp first on the line, but not every service
writes it the same way. All of these are valid and denote an instant:

- `2024-03-01T10:00:00` and `2024-03-01 10:00:00` (a `T` or a single space
  between date and time);
- with fractional seconds: `2024-03-01T10:00:00.250`;
- with a UTC marker: `2024-03-01T10:00:00Z`;
- with a numeric offset: `2024-03-01T12:00:00+02:00` (which is the same
  instant as `2024-03-01T10:00:00Z`).

A timestamp with no `Z` and no offset is in UTC. `--since` / `--until`
accept the same forms. The report orders entries by instant, and its
`first` / `last` fields are the timestamps (as written in the log) of the
earliest and latest entries.

## Development

```
python -m pytest -q
```

## Config

`--json-summary` used to switch the `report` command to JSON output before
the dashboard moved to reading `report.csv` directly. It is still accepted
but has no effect on the current text report.
