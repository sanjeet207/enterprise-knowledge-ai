# Changelog

## Unreleased

### Added
- Document versions (a new version inherits level and team and archives the old one) and a comparison of any two readable documents: changes found by code, summary checked for invented figures.
- Single sign-on (OpenID Connect with PKCE) for Entra ID and compatible providers, account linking by stable subject id, SSO-only accounts, `PASSWORD_LOGIN_ENABLED`. See docs/SSO.md.
- Observability: request ids, JSON request logs, `/ready`, token-protected `/metrics`.
- Data governance: personal data download and erase, retention purge script, document review dates with overdue counts.
- Saved multi-turn conversations with follow-up understanding (the condenser sees only the person's earlier questions) and Helpful / Not helpful feedback on answers, with ratings in administrator insights.
- Document upload (PDF, Word, text, Markdown, CSV) and an administration screen: people, levels, teams, documents, and an administrator activity log. Administrators publish company-wide documents; engagement managers add to their own team only.
- Administrator flag on users, separate from the reading level (`users.is_admin`, `admin_events` table). Run `python -m scripts.init_db` to upgrade an existing database.
- Demo accounts `admin@acme.test` and `admin@globex.test`.
- Maker-checker approval for uploads by engagement managers; sign-in lockout (5 failures, 15 minutes); per-person question limit; administrator insights (usage, content gaps).
- Smoke test grows to cover publishing rules.
- Question router: document questions go to retrieval; general questions are answered by the model and
  clearly labelled "General knowledge" with no sources; company, live-information and override questions are refused.
- Plain-code question analysis: answer depth (quick, standard, deep) and format (short, list, steps, compare).
- One-command setup (`scripts/quickstart.sh`) and an end-to-end smoke test (`scripts/smoke_test.py`, 17 checks).
- Persistent reranker model cache with self-healing and warm-up.
- LICENSE (MIT), SECURITY.md and this changelog.

### Changed
- Evaluation set grew from 80 to 86 questions; result 86/86 with 0 access leaks.
- Evaluation outputs moved to `evaluation/`.
- Unit tests: 189.
- `POST /documents/ingest` now follows the same publishing rules as an upload.

### Removed
- Unused API-key setting. The system runs on a local Ollama model.

## Earlier

- Hybrid search (vector + keyword, RRF) with reranking.
- Access control by tenant, level and engagement team; JWT login; audit log.
- Grounded answers with citations, per-claim validator, refusal threshold, bounded retries.
- CI: unit tests, access checks against Postgres + pgvector, Docker build.
