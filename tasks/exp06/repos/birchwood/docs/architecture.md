# Architecture

A site widget calls `GET /v1/slots?room=<id>&day=<date>` and `POST /v1/holds`.
The service keeps rooms, slots and holds in Postgres (see ADR-0004) behind
`birchwood.store`. A hold expires after 15 minutes unless confirmed.

```
widget -> birchwood (HTTP) -> store -> Postgres
```

Background expiry runs every minute in-process; there is no separate worker.
