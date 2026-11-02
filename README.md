# Enterprise Knowledge AI Platform

[![CI](https://github.com/sanjeet207/enterprise-knowledge-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/sanjeet207/enterprise-knowledge-ai/actions/workflows/ci.yml)

A secure internal "company brain". Employees ask questions in plain language and get answers **only from their company's own documents**, **with citations**, and **only from documents they are allowed to see**. Access depends on the person's clearance level and, for sensitive material, on whether they are on the engagement team. Off-topic questions are refused, answers are verified before they are shown, and every question is written to an audit log.

> **About the data.** Everything in this repository is fictional. The demo company, "Acme Financial Services", and its fourteen policy documents were written for this project, as were the demo users and their shared password (`DemoPass2026x`, for local use only). A second tenant, "Globex" (two documents), exists to test tenant isolation.

---

## What makes it different from a basic RAG demo

| Concern | How it is handled |
|---|---|
| **Who can see what** | Access is enforced **inside the SQL query** (tenant, clearance level, engagement team). Documents a user may not see are never fetched, so no model can leak them. |
| **Refusals reveal nothing** | "No results" and "not relevant" produce the *identical* refusal text, so a refusal never reveals that a restricted document exists. |
| **Answers are grounded** | Every factual sentence must carry a `[n]` citation (checked in plain code). A validator then checks each claim against its sources. |
| **Failing safe** | If an answer cannot be verified after bounded retries, nothing is shown (`unverified`) rather than a guess. |
| **Prompt injection** | Retrieved text and user questions are treated as data. Injection attempts are part of the evaluation set. |
| **Auditability** | Every question is logged with its outcome, sources, timings and a step-by-step agent trace, viewable by a Director. |
| **No vendor lock-in** | Runs entirely on a local model (Ollama, `qwen2.5:7b`). No API key is needed. |

## Architecture

```mermaid
flowchart TB
  U["User: chat UI<br/>JWT carries only the user id"]
  C["1 Corrector (LLM)<br/>fixes typos, guarded by a similarity check"]
  R["2 Retriever (code)<br/>hybrid search + rerank<br/>access filtered in SQL"]
  T{"Top score ≥ 0.1?"}
  W["Rewriter (LLM)<br/>up to 3 reworded searches"]
  A["3 Answerer (LLM)<br/>cited answer from passages only"]
  CR["4 Citation rule (code)<br/>every factual sentence needs [n]"]
  V["5 Validator (LLM + code)<br/>per-claim check + citation overlap"]
  REF["Refused<br/>identical text, reveals nothing"]
  UNV["Unverified<br/>fail closed, nothing shown"]
  OK["Answered<br/>with citations and sources"]
  LOG[("audit_log<br/>outcome, sources, agent trace")]
  DB[("Postgres + pgvector<br/>documents, chunks, users")]
  LLM["Ollama qwen2.5:7b<br/>local, JSON-schema output"]

  U --> C --> R --> T
  T -- yes --> A
  T -- no --> W
  W -- "retry search" --> R
  W -- "still weak" --> REF
  A --> CR
  CR -- "missing citation: retry" --> A
  CR --> V
  V -- "rejected: reason sent back, max 2 retries" --> A
  V -- "retries used up" --> UNV
  V -- supported --> OK
  OK --> LOG
  REF --> LOG
  UNV --> LOG
  R --- DB
  C -.- LLM
  A -.- LLM
  V -.- LLM
  W -.- LLM
  P["Planner (LLM, optional)<br/>off by default"]
  R -.- P
  classDef code fill:#e6f4ea,stroke:#2e7d32
  classDef llm fill:#e8eaf6,stroke:#3949ab
  classDef out fill:#fff3e0,stroke:#ef6c00
  class R,CR code
  class C,W,A,V,P llm
  class REF,UNV,OK out
```

Green boxes are plain code, blue boxes are model agents. The **orchestrator is plain code, not a model**: permissions, retry limits and the audit record are never delegated to an LLM. Agents may only choose within fixed tools and limits ("bounded agency").

### How a question is answered

1. **Login.** Login returns a short-lived JWT (60 minutes) that carries only the user id. Tenant, clearance level, engagement team and active status are read from the database on every request, so a role change or a deactivation takes effect immediately.
2. **Corrector.** Fixes typos. Code rejects the fix if it changes the meaning.
3. **Retriever.** Hybrid search (keyword + vector, merged with Reciprocal Rank Fusion), then a cross-encoder rerank. Hierarchical chunking: small chunks are searched, their larger parent passage is returned.
4. **Refusal check.** A top rerank score below `0.1` refuses without calling the answering models. A weak score first triggers the rewriter (up to 3 reworded searches).
5. **Answerer.** Writes an answer from the retrieved passages only, citing `[n]`.
6. **Citation rule.** Code requires a citation on every factual sentence.
7. **Validator.** A model checks each claim as strict JSON (fail-closed), and code checks each citation points at a passage that contains the sentence's words. A rejection sends the reason back to the answerer; at most 2 retries.
8. **Outcome and audit.** `answered`, `refused`, `no_answer`, `unverified` or `error`, written to `audit_log` with the full agent trace.

## Access model

| Level | Role | Sees |
|---|---|---|
| 1 | Analyst | Level-1 documents (company-wide policies) |
| 2 | Manager | Levels 1–2 (procedures, procurement, KYC) |
| 3 | Director | Levels 1–3 (compensation, attrition, risk) |
| 4 | Partner | Levels 1–4 (board minutes) |

Plus **tenant isolation** (a Globex user never sees Acme documents) and **engagement-team access**: the Project Titan valuation memo needs level 3+ *and* membership of the Titan deal team. A partner who is not on the team cannot see it.

`scripts/verify_access.py` checks this independently of the SQL: every demo user searches every document's topic, and must never see a document the rule forbids (**160 checks**, run in CI against a real Postgres).

## Evaluation

`python -m scripts.evaluate` asks the running API 80 questions as real demo users and scores the responses.

| Metric | Result |
|---|---|
| Answer accuracy (37 answerable questions, incl. 6 with typos) | **100%** (37/37) |
| Citation accuracy (answer cites the expected document) | **100%** (37/37) |
| Refusal accuracy (14 restricted, 5 off-topic, 7 injection) | **100%** (26/26) |
| **Access leaks** (a forbidden fact appears in an answer) | **0** |
| Multi-part questions (every part answered and cited) | **100%** (6/6) |
| No-answer guard (8 questions the documents cannot answer, no invented facts) | **100%** (8/8) |
| Injection hidden in a valid question (no leak) | **100%** (3/3) |
| Median latency, answered / refused | 6.8 s / 2.4 s |

Measured on a MacBook Pro (M3, 16 GB) with `qwen2.5:7b` via Ollama.

**What the evaluation found along the way** (each fix was driven by a failing case):

- Typo-heavy questions were refused until the corrector and a rewriter safety net were added.
- A validator that judged all claims in one free-text reply produced false rejections; per-claim JSON verdicts plus a deterministic citation check fixed it (7/7 planted-error cases).
- Multi-part questions went **4/6 → 6/6** after two changes found by reading the audit trace: a plain-code rule that every sentence needs a citation, and sending the validator's objection back to the answerer on retry (at temperature 0, an unchanged retry just repeats the same answer).
- A **bounded planner agent** (a search-or-finish tool loop) was built and measured fairly with an on/off comparison. It gave **no gain** (4/6 with and without it) and cost about 2 s per question, so it is **off by default** (`PLANNER_ENABLED=true` turns it on).

### Honest limitations

- The 80 questions were written by the author against the same 16 documents (14 Acme, 2 Globex), so 100% means "no regressions on this suite", not "perfect in general". An independently written question set is the next improvement to the evaluation.
- The corpus is small and fictional. No claim is made about scale.
- Latency is that of a local 7B model on a laptop. A hosted model would be faster; the agents are model-agnostic through a per-agent model setting (`<AGENT>_MODEL`).
- The model-based evaluation is **not** run in CI (the 7B model is too slow on hosted runners). CI runs the unit tests, the access-control sweep and the image build; the evaluation is run locally before a release.

## Quick start (local)

Requirements: Python 3.12, Docker, [Ollama](https://ollama.com).

```bash
git clone https://github.com/sanjeet207/enterprise-knowledge-ai.git
cd enterprise-knowledge-ai
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# put a random secret (32+ characters) into JWT_SECRET in .env, e.g.:
python -c "import secrets; print(secrets.token_urlsafe(48))"

docker compose up -d db          # Postgres + pgvector
ollama pull qwen2.5:7b           # about 5 GB, one time
python -m scripts.init_db        # creates every table (safe to re-run)
python -m scripts.seed_demo      # demo tenants, users and documents

uvicorn app.main:app --port 8000
# open http://127.0.0.1:8000
```

### Demo accounts

Password for all: `DemoPass2026x` (local demo data only).

| Email | Level | Notes |
|---|---|---|
| `analyst@acme.test` | 1 | company-wide policies only |
| `manager@acme.test` | 2 | |
| `director@acme.test` | 3 | can open the audit view |
| `director_titan@acme.test` | 3 | on the Project Titan deal team |
| `partner_titan@acme.test` | 4 | on the deal team |
| `partner_outsider@acme.test` | 4 | level 4 but **not** on the deal team |
| `globex_analyst@globex.test` | 1 | other tenant |

Try the same question as different users: for example *"What is the indicative valuation of Project Titan?"* as `director_titan` (answered, cited) versus `director` (refused).

### Tests and checks

```bash
python -m pytest -q tests             # 54 unit tests, no database or model needed
python -m scripts.verify_access       # 160 access-control checks (needs the database)
python -m scripts.check_validator     # planted-error check for the validator (needs Ollama)
python -m scripts.evaluate            # the 80-question evaluation (needs the server and Ollama)
python -m scripts.evaluate --only multi_part --workers 3   # a category, in parallel
```

### Docker

`docker compose --profile app up -d --build` builds and starts the API container next to the database (it reaches Ollama on the host through `host.docker.internal`). CI verifies that the image builds; a full deployed run on Azure is on the roadmap.

## Continuous integration

GitHub Actions runs on every push: **unit tests**, **access-control checks against a real Postgres with pgvector** (the job fails on any leak), and a **Docker image build**.

## Project layout

```
app/
  agents/        corrector, retriever, rewriter, planner, answerer, validator, orchestrator
  routers/       auth, chat, documents, retrieval, audit (FastAPI)
  services/      vector store (SQL access control), embedder, reranker, LLM client, audit, answer checks
  static/        chat UI (login, sources panel, outcome states, audit view)
scripts/         init_db, seed_demo, verify_access, check_validator, evaluate
tests/           unit tests and the 80-question evaluation set
```

## Roadmap

- [x] Hybrid retrieval with reranking, access control in SQL, JWT login
- [x] Grounded answers, citation rule, claim validator, refusal threshold, audit log with agent trace
- [x] Evaluation suite (80 questions) and CI
- [ ] Azure deployment with a spending cap
- [ ] Tracing dashboard (OpenTelemetry / Langfuse) and a model router
- [ ] Document upload (private per user, injection-hardened) and an admin page
- [ ] An independently written evaluation set and broader adversarial security tests

## Tech

Python 3.12 · FastAPI · PostgreSQL 16 + pgvector (HNSW) · psycopg 3 · sentence-transformers (`all-MiniLM-L6-v2`) · FlashRank reranker · Ollama (`qwen2.5:7b`) · JWT · Docker · GitHub Actions
