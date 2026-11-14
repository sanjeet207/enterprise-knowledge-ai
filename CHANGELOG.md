# Changelog

## Unreleased

### Added
- Embedding provider switch: `EMBEDDING_PROVIDER=ollama` serves embeddings (e.g. nomic-embed-text, bge-m3) from Ollama; `scripts/reindex_embeddings.py` re-embeds stored chunks without re-uploading; `scripts/retrieval_eval.py` measures retrieval alone (right document in the top results, MRR).
- Refiner agent (off by default, `REFINER_ENABLED=true`): after a question is accepted as being about the company, the model rewrites it into its clearest form; plain code rejects a rewrite that adds or drops a number, loses part of the question, or looks like an answer. A search with the refined wording is merged into the passages. Measured: no gain (86-question answerable 37/37 -> 36/37, +4 s per answer), so it stays off.

### Changed
- Questions not about the company are refused by default. `GENERAL_ENABLED` now defaults to false; smoke test and evaluation expect a refusal unless it is set to true.

### Added
- Technical self-audit (`docs/TECHNICAL_AUDIT.md`). Fixed: a worker killed mid-upload could leave half a document searchable and the retry reported it done (chunks are now written hidden and published in one statement); a slow worker could overwrite a job another worker owned. `scripts/crash_test.py` simulates the kill. `scripts/reproduce.sh` runs every check and saves logs to `evaluation/logs/`.
- Found by the second question set: pay questions are now treated as company questions (never answered from general knowledge); the citation check no longer penalises words the question itself used; one quick retry when the model server drops a request. `scripts/diagnose.py` shows every step for one question. A prompt rule for comparing amounts was tried and removed because it lowered accuracy.
- Independent evaluation kit: `evaluation/QUESTION_BRIEF.md` for a person who writes questions, a CSV template, `scripts/import_questions.py` (checks the sheet and builds the set), `scripts/export_documents.py`, and `evaluate --tag` for a separate report.
- Tracing: every request, model call, retrieval step and upload job becomes a span in a trace, sent as standard OTLP to Jaeger or any compatible backend (`app/tracing.py`, `docs/TRACING.md`, `docker-compose.tracing.yml`). Off by default. Spans never contain questions, answers, document text or names. `X-Trace-ID` header and `trace_id` in request logs.
- Security review and hardening: prompt-wrapper breakout fixed, zip/PDF bomb limits, administrator grant ceiling (`ADMIN_MAX_GRANT_LEVEL`), upload scan and reviewer model (`agents/inspector.py`, `INSPECT_UPLOADS`, `scripts/check_inspector.py`) for planted instructions, rate limit on search, browser security headers, `API_DOCS_ENABLED`. New `scripts/security_probe.py` (live attacks) and `docs/SECURITY_REVIEW.md`.
- Background document processing: uploads return 202 with a job id and are indexed by a worker (PostgreSQL job queue with SKIP LOCKED, retries with back-off, stuck-job recovery, permissions re-checked when the job runs, idempotent retries). `GET /documents/jobs`, `scripts/worker.py`, `INGEST_ASYNC`, `INGEST_WORKER_ENABLED`.
- Research assistant: a planner splits a broad request into questions, each answered under the asker's own access rules; cited, checked draft report with evidence gaps and possible inconsistencies; saved privately; included in data export and erase. `scripts/evaluate_research.py` and `tests/research_set.json`.
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
