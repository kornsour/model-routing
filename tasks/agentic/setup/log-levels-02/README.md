# logproc

![Build](https://img.shields.io/badge/build-failing-red)

A small, dependency-free package for parsing app log lines, aggregating them
into per-level counts, exporting to CSV, and pushing a batch summary to a
(simulated) remote metrics endpoint.

## Layout

- `src/logproc/parser.py` - parses `"TIMESTAMP LEVEL message"` log lines.
- `src/logproc/aggregate.py` - counts entries by level; pagination over them.
- `src/logproc/csvexport.py` - CSV export of parsed entries.
- `src/logproc/timestamps.py` - timestamp parsing shared by the report.
- `src/logproc/pipeline.py` - reads a log file, writes entries, builds a report.
- `src/logproc/retry.py` - retry-with-backoff helper for the remote push.
- `src/logproc/cli.py` - the `logproc` command-line tool.

## Usage

```
python -m logproc.cli process app.log --out entries.csv
python -m logproc.cli report app.log
```

## Levels

The summary counts entries under five canonical levels, in increasing
severity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

Not every service spells them that way. The gateway (Go) writes `WARN`,
`ERR` and `FATAL`; the batch jobs (Java) write `WARN` and `SEVERE`. These
are aliases, not extra levels:

| written in the log | canonical level |
|---|---|
| `WARN` | `WARNING` |
| `ERR` | `ERROR` |
| `FATAL`, `SEVERE` | `CRITICAL` |

Anything else in the level position (`TRACE`, `NOTICE`, a stray word) is
not a log line as far as logproc is concerned and is skipped.

## Development

```
python -m pytest -q
```

## Config

`--json-summary` used to switch the `report` command to JSON output before
the dashboard moved to reading `report.csv` directly. It is still accepted
but has no effect on the current text report.
