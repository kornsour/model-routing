# trackbook

A small run ledger for ML experiments: record a run, update it as it finishes,
diff two runs, and keep the provenance needed to reproduce one.

## API

- `POST /runs` records a run. `started_at` defaults to the time the server
  receives the request.
- `GET /runs/{id}` returns a run.
- `PATCH /runs/{id}` updates `status` and `ended_at`.

A run's `ended_at` reads `0001-01-01T00:00:00Z` until the run ends.

## Development

```bash
gofmt -l . && go vet ./... && go test -race ./...
python3 -m unittest discover -s python/tests -v
```
