# One-time migration: SQLite to Postgres

**Status: completed 2026-03-02.** Production has run on Postgres since then;
the SQLite file was deleted from the VM on 2026-03-16.

Steps we ran:

1. Freeze writes (`birchwood maintenance on`).
2. `birchwood export --sqlite /var/lib/birchwood/db.sqlite > dump.json`.
3. `birchwood import --postgres "$DATABASE_URL" < dump.json`.
4. Point `DATABASE_URL` at Postgres and restart.
5. `birchwood maintenance off`.
