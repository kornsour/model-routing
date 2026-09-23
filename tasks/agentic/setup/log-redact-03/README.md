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
- `src/logproc/redact.py` - masks secrets in log messages.
- `src/logproc/errors.py` - the most frequent error messages in a log.
- `src/logproc/cli.py` - the `logproc` command-line tool.

## Usage

```
python -m logproc.cli process app.log --out entries.csv
python -m logproc.cli report app.log
python -m logproc.cli errors app.log --limit 5
```

`errors` prints the most frequent `ERROR` messages in a log, most frequent
first (ties in order of first appearance), one per line as
`<count>  <message>` (the count, two spaces, the message).

## Redaction

Log messages can carry credentials. Anything that leaves the machine - the
entries CSV written by `process` and the output of `errors` - shows messages
with every secret masked:

- A `key=value` pair is a secret when the key, compared case-insensitively,
  is `password`, `passwd`, `secret`, `token`, `api_key` or `apikey`, or ends
  in `_password`, `_secret` or `_token` (e.g. `access_token`,
  `client_secret`). A key is the run of letters, digits, `_` and `-`
  directly before the `=`.
- The value is everything after the `=` up to the next whitespace, `&` or
  `;` (or the end of the message).
- `Authorization: Bearer <credentials>` and `Authorization: Basic
  <credentials>` (any capitalization) carry a secret: the credentials, up to
  the next whitespace.

A masked secret keeps everything around it exactly as written, including
the key, the `=` and the `Authorization: Bearer ` prefix; only the secret
itself is replaced by `***`. For example
`login failed user=bob Password=hunter2; retry=3` becomes
`login failed user=bob Password=***; retry=3`.

## Development

```
python -m pytest -q
```

## Config

`--json-summary` used to switch the `report` command to JSON output before
the dashboard moved to reading `report.csv` directly. It is still accepted
but has no effect on the current text report.
