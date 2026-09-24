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
- `src/logproc/fields.py` - durations (`took=...`) carried in log messages.
- `src/logproc/latency.py` - latency percentiles and the slow-request filter.
- `src/logproc/cli.py` - the `logproc` command-line tool.

## Usage

```
python -m logproc.cli process app.log --out entries.csv
python -m logproc.cli report app.log
python -m logproc.cli latency app.log
python -m logproc.cli slow app.log --over 250ms
```

## Latency

Services record how long a request took as `took=<number><unit>` anywhere
in the message. The number may have a fractional part and the unit is one
of `us`, `ms` or `s` - e.g. `took=850us`, `took=12ms`, `took=1.25s`. Entries
without a duration are ignored by both commands below.

- `latency` prints one line, `count=<n> p50=<ms> p90=<ms> p99=<ms>
  max=<ms>`, over every entry that carries a duration, all values in
  milliseconds (written the way Python's `format(value, "g")` writes them).
  Percentiles use the nearest-rank method: the p-th percentile is the
  smallest recorded duration such that at least p% of all recorded durations
  are less than or equal to it. With no durations it prints `count=0`.
- `slow --over <threshold>` prints, in log order, every entry that took
  strictly longer than the threshold, as `TIMESTAMP LEVEL message`. The
  threshold is written the same way as a duration (`250ms`, `0.5s`, ...).

## Development

```
python -m pytest -q
```

## Config

`--json-summary` used to switch the `report` command to JSON output before
the dashboard moved to reading `report.csv` directly. It is still accepted
but has no effect on the current text report.
