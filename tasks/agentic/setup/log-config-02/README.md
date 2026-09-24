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
- `src/logproc/config.py` - `logproc.toml` discovery and the output-path rules.
- `src/logproc/cli.py` - the `logproc` command-line tool.

## Usage

```
python -m logproc.cli process app.log --out entries.csv
python -m logproc.cli report entries.csv
```

## Config

Where `process` writes its entries CSV is decided by these rules, first
match wins:

1. `--out PATH` on the command line.
2. The `LOGPROC_OUT` environment variable, when it is set to a non-empty
   value. An empty `LOGPROC_OUT` is the same as an unset one (the on-call
   wrapper always exports it, sometimes blank).
3. `path` under `[output]` in the nearest `logproc.toml`, looking in the
   working directory and then each parent directory in turn. A relative
   `path` is relative to the directory that holds that `logproc.toml`, not
   to the working directory, so `logproc process` gives the same answer
   from any subdirectory of a project.
4. Otherwise `entries.csv` in the working directory.

Example `logproc.toml`:

```toml
[output]
path = "out/entries.csv"
```

`--json-summary` used to switch the `report` command to JSON output before
the dashboard moved to reading `report.csv` directly. It is still accepted
but has no effect on the current text report.

## Development

```
python -m pytest -q
```
