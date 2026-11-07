# Changelog

## Unreleased

### Added
- Question router: document questions go to retrieval; general questions are answered by the model and
  clearly labelled "General knowledge" with no sources; company, live-information and override questions are refused.
- Plain-code question analysis: answer depth (quick, standard, deep) and format (short, list, steps, compare).
- One-command setup (`scripts/quickstart.sh`) and an end-to-end smoke test (`scripts/smoke_test.py`, 17 checks).
- Persistent reranker model cache with self-healing and warm-up.
- LICENSE (MIT), SECURITY.md and this changelog.

### Changed
- Evaluation set grew from 80 to 86 questions; result 86/86 with 0 access leaks.
- Evaluation outputs moved to `evaluation/`.
- Unit tests: 114.

### Removed
- Unused API-key setting. The system runs on a local Ollama model.

## Earlier

- Hybrid search (vector + keyword, RRF) with reranking.
- Access control by tenant, level and engagement team; JWT login; audit log.
- Grounded answers with citations, per-claim validator, refusal threshold, bounded retries.
- CI: unit tests, access checks against Postgres + pgvector, Docker build.
