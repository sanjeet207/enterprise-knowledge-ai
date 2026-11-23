# Security model

One page: the rules the system enforces, where each is enforced, and which evidence shows it works.
The trust boundaries, actors and full threat list are in [THREAT_MODEL.md](THREAT_MODEL.md). This page does not repeat them.
Everything here is the author's own assessment; no independent review has been done yet (see `docs/SECURITY_REVIEW.md`
for what was found in self-review).

## Rules

| # | Rule | Enforced in | Evidence |
|---|---|---|---|
| 1 | Identity comes from a signed token; level, active status, tenant and team are read from the database on every request. | `app/security.py: get_current_user` | matrix M1, M3, M4 |
| 2 | A person only retrieves passages that are in their company, published, at or below their level, and in their team if the document has one. The filter is in the SQL query, before any ranking or model. | `app/services/vector_store.py`, `app/services/versions.py` | `scripts/verify_access.py` (CI), matrix M1, M4, M8; `scripts/scale_test.py` (no leaks across 30,000 other-company documents) |
| 3 | Models never decide access. They only see passages the query already returned. | orchestrator, research agent | threat model section 3; matrix M13 |
| 4 | Saved material is re-checked when loaded: access lost later hides the answer, finding or export. | `conversations.py`, `reports.py`, `governance.py` | `docs/SECURITY_REVOCATION_TEST_RESULTS.md` |
| 5 | Managing is not reading: administrators publish, approve and manage people and teams but sit at level 1 for reading. A non-admin upload waits for a different administrator. | `require_admin`, `ingest.status_for`, `admin.approve_document` | matrix M15; `docs/security/AUTHORIZATION_COVERAGE.md` |
| 6 | A person cannot widen their own access: no self-service level change, no team creation, no self-approval. An access request records a wish only. | `routers/admin.py`, `routers/access.py` | matrix M2, M11, M12 |
| 7 | An uploader can delete or re-version their own document only while they can still read it. | `upload_policy.can_delete` | matrix M20, M20a |
| 8 | Errors do not reveal what exists: a missing and a forbidden document give the same 404; the duplicate-upload error names a document only to someone who can read it. | routers, `ingest.duplicate_message` | matrix M16, M17, M19 |
| 9 | Uploaded text is scanned for instructions to an AI, then (when enabled) checked by a reviewer model; flagged files are held for a second administrator. | `content_scan.py`, `inspector` | threat model; `tests/` injection cases; evaluation injection rows |
| 10 | Every question and every administrative action is logged; the audit log is readable by level 4 only, per company, and exports carry no answers. | `audit`, `admin.record`, `/audit/*` | matrix M12; `tests/test_audit_export.py` |
| 11 | People can export and erase their own data; old audit rows and conversations are purged on a schedule (`RETENTION_DAYS`, default 365). | `/me/data`, `/me/erase`, `scripts/purge_retention.py` | unit tests for the redaction; **no live test of the endpoints** |
| 12 | Brute force and flooding are limited: login lockout after repeated failures; a shared per-person request budget on search, chat, compare and research. | `security.py`, `chat.limiter` | `tests/test_lockout_ratelimit.py` |

## How the checks are run

- **Every push (GitHub Actions):** all unit tests; `verify_access` against Postgres; the live security matrix against a
  real server, for the rows that need no language model. Any failure blocks the build.
- **Before a release (on the author's machine):** the full matrix, which also covers chat answers, saved-answer hiding
  and the research assistant (it needs the language model). Latest run: 34/34 (`evaluation/SECURITY_MATRIX_RESULTS.md`).

## Known gaps

- No independent review; no external penetration test.
- Rule 11's endpoints are not exercised by a live test; SSO is tested with unit tests, not against a live identity provider.
- The matrix runs against one demo company with a local model, so it shows the behaviour exists, not that every
  configuration is covered.
- Prompt injection is reduced by layers, not eliminated. The evaluation measures it on a fixed set only.
- A confirmation oracle remains in the duplicate-upload message (it confirms the exact text exists).
