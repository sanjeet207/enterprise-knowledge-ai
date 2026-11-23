# Operations: what was tested, and what was not

Everything here was run on one MacBook (M3) against the local Docker database, with fictional data. None of it was run on a
cloud deployment. Each section says what is proven and what is only written down.

## Backup and restore (tested locally)

`bash scripts/backup_restore_drill.sh` dumps the database (`pg_dump`, custom format) to `backups/`, restores the dump into a
scratch database, compares the row count of every table and the number of indexes, and removes the scratch database.
Latest run, 2026-11-23: 744 KB dump in 1 s, restored in 1 s, 12 tables, same row counts, same index count (PASS).

Limits: the demo database is tiny, so the timings say nothing about a large one. Matching counts show the data came back; the
drill does not run a search against the restored copy. Dumps hold real data, so `backups/` is git-ignored and a dump must be
stored encrypted. On Azure Database for PostgreSQL the platform's own point-in-time restore is the first choice; this drill is
the portable fallback. Restoring into the live database (as opposed to a scratch one) has not been rehearsed.

## Model outage (tested locally)

`scripts/outage_drill.py` runs against a server whose model address points at nothing. Latest run (9/9): the service stays
healthy, sign-in and search keep working (search still hides restricted documents), a question gets a plain 503 in about 3 s with
no internal details, a question no readable document matches is refused as usual, and the server is healthy afterwards.

Hosted models add one more failure: rate limits. On Groq's free tier (30 requests a minute, 200,000 tokens a day per model) the
client waits as long as the provider asks (up to 30 s) and retries up to three times, then reports the same 503. This was
observed in a real run: roughly a third of the calls were rejected and every one succeeded on retry.

## Load (partly tested)

- Retrieval (no model): `python -m scripts.scale_test`, results in `evaluation/SCALE_REPORT.md`. At 10,000 documents a search
  took a median 29-61 ms; 8 simultaneous searches ran at about 83 per second with no errors and no leaks.
- Answers (model): not load-tested. A local 7B model answers one question at a time (median about 12 s), and each person is
  limited to 20 questions a minute (`CHAT_RATE_PER_MINUTE`). How many people the answer path can serve at once on a hosted model is
  unmeasured and, on the free tier, limited by the provider's quotas.

## Rollback (written, not rehearsed)

The application is one container image and the database schema is created by `scripts/init_db.py` (mostly additive migrations). To roll
back, deploy the previous image tag; on Azure Container Apps keep earlier revisions and switch traffic back
(`az containerapp revision list`, then activate the earlier revision and send it 100% of traffic). The migrations are
almost all additive (`ADD COLUMN IF NOT EXISTS`, with defaults), so an older image is expected to run against a newer schema,
but this was not tested; one migration (`migrate_auth.py`) also deletes duplicate accounts that share an email, which cannot
be undone by switching images. This has not been rehearsed
on Azure, and no rollback of a migration has been tested.

## Not covered

Monitoring and alerting, a recovery-time target, multi-replica behaviour (the rate limiter is in memory, per process), and any
failover of the database.
