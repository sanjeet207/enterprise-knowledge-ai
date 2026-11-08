# Technical self-audit

**Who did this and what it is.** A code review of four areas, written by the AI assistant that helped build the project.
It is a self-audit, not an independent one: the same hand wrote much of this code, so blind spots are likely. Its value is
that every claim below points at code you can read. An outside review is still wanted (see the README roadmap).

**Date:** 8 November 2026. **Scope:** permission enforcement, background-job recovery, the security fixes in
`docs/SECURITY_REVIEW.md`, and the research assistant. **Method:** reading the code paths end to end, then checking each
suspected weakness against the schema and the other code that touches the same data.

## Findings

| # | Severity | Finding | Status |
|---|---|---|---|
| A1 | Medium | **A worker killed half way through an upload left a half-written document.** Each parent chunk was committed on its own, so a process kill or power loss after chunk 1 left a partial document with the final status ("published" for an administrator's upload). Partial text was searchable. Worse, the retry found the document already existed (the idempotency check) and reported the job done, so the gap was never repaired. The existing clean-up only runs for ordinary exceptions. | **Fixed.** Chunks are now written as `indexing`, which no search, listing or comparison reads, and one `UPDATE` (`versions.promote`) makes them all visible together. A retry that finds `indexing` chunks deletes them and starts clean. `scripts/crash_test.py` simulates the kill and checks all of this. |
| A2 | Low | **A slow worker could overwrite a job another worker now owned.** A job running longer than the 30-minute stuck limit is handed to another worker, but when the first worker finished, its `done` or `failed` update matched on the id alone and could change the new owner's job. | **Fixed.** All three completion updates now add `AND status = 'processing'`. Double processing was already harmless (indexing is idempotent); this removes the confusing state. |
| A3 | Low | **Chunks left behind by a job that exhausts its retries after a crash stay as `indexing`.** They are invisible to every user, so this is wasted space, not a leak. | Open. A cleanup in `purge_retention` for `indexing` chunks older than a day would remove them. |
| A4 | Low | **Research reports number sources by title.** Two different documents with the same title would share one citation number. | Open, cosmetic: the report is still correct about which passages it used. |
| A5 | Medium | **Rate limit and sign-in lockout live in server memory.** Two web servers would each allow the full limit, and a restart resets lockouts. | Open, known. Needs Redis or an edge service; planned with the Azure step. |
| A6 | Info | **Tokens have no issuer or audience claim and cannot be revoked before they expire (60 minutes).** Mitigated: the user is reloaded from the database on every request, so deactivation and level changes take effect immediately; the algorithm is pinned. | Accepted. |
| A7 | Info | **Text extraction runs inside the upload request.** Bounded by file size, unpacked size, page and character limits. | Accepted, documented. |

## Checked and found sound

- **Access control in search.** `secure_hybrid_rrf_search` applies tenant, `status = 'published'`, level and team membership in the
  `allowed_parents` query that both the vector and the keyword search join to, and repeats the tenant filter on the chunks.
  All values are parameters, none are concatenated into the SQL.
- **Identity on every request.** `get_current_user` reloads the person from the database, rejects inactive accounts, and
  decodes with the algorithm pinned. The token carries only the user id.
- **Document actions.** Upload, delete, approve and version replacement all go through `upload_policy` / admin checks that
  read the person's current role; an administrator's grants are capped by `admin_policy.check_grant`.
- **Job queue.** The claim uses `FOR UPDATE SKIP LOCKED` in a single `UPDATE ... RETURNING`; retries, back-off and permanent
  failures are pure functions with unit tests; the uploader's account, level and team are re-read when the job runs, and
  `publish_status` takes the safer of what was promised and what is allowed now.
- **Research assistant.** It has no path to documents of its own: each question goes through `orchestrator.answer_question` as
  the same user and the same SQL-filtered retriever. A refused question and an empty search produce the same gap wording. Reports are
  read, reviewed and deleted only by `user_id`.

## What this audit did not do

- No dynamic testing beyond the existing probes, and no fuzzing.
- It did not review the web interface's JavaScript line by line (it uses no `innerHTML`, checked by a test).
- It did not review dependencies for known vulnerabilities. A scheduled dependency scan is on the roadmap.
- It cannot replace a person who did not write the code.
