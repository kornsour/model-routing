# ADR-0004: Move bookings to Postgres

Status: Accepted. Supersedes [ADR-0001](0001-use-sqlite.md).

Three studios now share one service and SQLite's single writer shows up as
lock timeouts at opening hour. Postgres gives us concurrent writers and
point-in-time backups.
