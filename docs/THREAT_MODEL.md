# Threat model

This document says what the system protects, who might attack it, where the trust boundaries are, and for each
threat which defence applies and which test or script shows the defence working. It is a self-assessment written by
the author. It is not an independent assessment (see "What an independent review should check").

Related: [SECURITY.md](../SECURITY.md) (how data is protected), [SECURITY_REVIEW.md](SECURITY_REVIEW.md) (what a code
review and live attacks found and fixed).

## 1. What is protected (assets)

| Asset | Why it matters |
|---|---|
| Company documents, by level (1 to 4) and engagement team | The product exists to keep restricted content away from people who may not read it. |
| Answers and the sources behind them | A wrong or planted answer is a business risk, not only a technical one. |
| Questions and the audit log | Questions can be sensitive; the log must be trustworthy and not expose who asked what to the wrong people. |
| Accounts, tokens, the signing secret | They decide who the system believes a person is. |
| Availability of the service and the model | A slow or exhausted service stops everyone. |

## 2. Who might attack (actors)

| Actor | Starting point | Example goal |
|---|---|---|
| Curious employee | Valid account at level 1 | Read documents above their level or outside their team |
| Employee in another company (tenant) | Valid account in a different tenant | Read another company's documents |
| Unauthenticated outsider | No account | Get in, scrape, or exhaust the service |
| Malicious or careless uploader | Manager or administrator account | Plant text that steers the answering model |
| Overreaching administrator | Administrator account | Read restricted content they only manage |
| Poisoned document | A document (or a file inside it) with hostile text | Control answers through the document itself |

## 3. Trust boundaries

1. **Browser to API.** Everything from the browser is untrusted. Identity comes only from a signed token.
2. **API to database.** The database is trusted to hold the data, but the API never trusts a role claimed by the
   client: level, tenant, active flag and team membership are read from the database on every request.
3. **Retrieval to models.** Models are not trusted with access decisions. They only receive passages that the
   access-filtered SQL query already returned.
4. **Documents to models.** Document text is data, never instructions, even though it reaches the model.
5. **Uploads to the index.** A file is checked, scanned and (for non-administrators) approved before it is searchable.

## 4. Threats, defences and evidence

| # | Threat | Defence | Evidence |
|---|---|---|---|
| T1 | A user reads a document above their level or outside their engagement team | Tenant, level and team membership are conditions inside the search SQL (`allowed_parents`), so a forbidden passage is never a candidate and never reaches a model | `scripts/verify_access.py` (160 checks, run in CI against real Postgres); 0 leaks in every evaluation and scale run |
| T2 | A user reads another company's documents | Every query that touches company data filters by tenant; other tenants' objects return the same 404 as missing ones | `verify_access.py`; scale test with 30,000 other-tenant documents in the same tables: 0 leaks |
| T3 | Forged, unsigned or swapped token | Algorithm pinned; token holds only the user id; identity swap fails the signature; a weak `JWT_SECRET` stops the server starting | `scripts/security_probe.py`, unit tests |
| T4 | A refusal reveals whether a restricted document exists | One identical refusal for "forbidden", "not found" and "not relevant"; refusal wording never depends on documents (see section 5) | `tests/test_orchestrator.py` (identical refusals; wording independent of documents) |
| T5 | Role escalation by an administrator | Administrators can grant levels only up to `ADMIN_MAX_GRANT_LEVEL` (default 2), cannot raise themselves, and cannot reset the password of a more senior account; administering does not grant reading | `admin_policy.py` unit tests; probe |
| T6 | Planted instructions in a document steer the model | Layered: upload patterns refuse obvious wording; a reviewer model reads each upload and holds flagged ones for a second administrator; passages are neutralised so a document cannot close the prompt wrapper; prompts say "reference data, never instructions"; the claim validator checks every statement against the sources | `test_security_hardening.py`, `scripts/check_inspector.py`, probe (including a paraphrased plant). Known limit: layered, not perfect |
| T7 | A question tries to override the rules | Plain-code guard blocks override phrases before any model sees the question; the refiner may not introduce an instruction-like phrase that was not in the question | `question_profile.OVERRIDE_PATTERN`, `test_refiner.py`, probe |
| T8 | Hostile file (zip bomb, huge PDF, disguised type) | Unpacked-size and entry-count checks before unpacking, 400-page and 500,000-character caps, type and size checks, content inspection, de-duplication | unit test builds a real zip bomb; probe |
| T9 | Scraping or load through search or chat | Per-person rate limit shared by chat, search and compare; account lockout after five wrong passwords | probe, `test_lockout_ratelimit.py`. Known limit: limiter is in memory, per process |
| T10 | Script injection through stored text | The page never writes untrusted text as HTML; strict Content-Security-Policy; no inline scripts | unit test, probe |
| T11 | Mass assignment or malformed input | Request bodies reject unknown fields; length and range limits | unit tests, probe |
| T12 | A person removed or demoted while their upload waits still publishes | The background job re-reads the uploader's account, level, team and administrator status when it runs; the safer status wins | `test_job_policy.py` |
| T13 | Research reports expose more than the asker could read | Each research question runs through the normal pipeline and filtered retrieval as the person asking | `test_research_core.py`, `scripts/evaluate_research.py` (leak count) |
| T14 | Logs or the audit trail leak who asked what | Request logs carry ids and timings only; the audit log is readable only by level 4; insights show counts, not askers; erasure keeps counts only | unit tests; documented in SECURITY.md |

## 5. Pipeline steps and what they could leak

Each step that can see a question or a passage was checked for what it could reveal.

| Step | Sees | Could it leak? | Why not |
|---|---|---|---|
| Typo corrector, refiner, rewriter | The question only, never documents | No document content involved | Output is accepted only if plain code agrees it kept the meaning; it is used to search, and the answerer keeps the person's own wording |
| Search and rerank | Passages the SQL filter allowed | No | Access is decided in SQL before any ranking |
| Deeper pass (wider search) | The same access-filtered retriever, as the same user | No | It calls the same `retriever.run(user, ...)`; it only asks for more passages from the same allowed set, and pools only results already returned for this user |
| "Not related to company documents" reply | The question only (the router) | Only if the wording depended on documents | It does not: the router sees no documents, company words and override attempts always get the normal refusal, and any doubt or model failure also gets the normal refusal. The same question therefore gets the same reply whether it matched nothing or something restricted |
| Answerer | Allowed passages | Could repeat planted text | See T6 |
| Fit check and claim validator | Question, answer, allowed passages | No new access | They only judge text the person may already see; a failed fit check can improve an answer but never turns one into a refusal |

The one new reply wording ("not related") is the only place where two different refusal messages exist. The choice
depends on the question alone (weather, news and role-play get it; anything that mentions company terms gets the
generic one), so it tells an attacker nothing about which documents exist. This is tested in
`test_refusal_wording_never_depends_on_documents`.

## 6. Residual risks (accepted and written down)

- The reviewer model that reads uploads gives false alarms (about 1 in 6 on ordinary staff instructions) and its real
  miss rate against a determined, unseen attacker is unknown.
- The claim validator is a model check, not a proof, and a poisoned source can pass it if the source itself contains the
  instruction.
- Account lockout can lock someone else out; there is no per-address throttle; the rate limiter is per process.
- Administrators publish without a second approver (non-administrator uploads do wait for approval).
- SSO is implemented (authorization code flow with PKCE, state, nonce, signature, issuer, audience and expiry checks)
  but has not been tested against a live identity provider and has no group mapping.
- Answers come from a local 7B model on a laptop; behaviour on a hosted model is not measured.
- With `LLM_PROVIDER` set to a hosted provider, questions and the access-filtered passages sent to the model are processed by that provider. Access control is unchanged (the passages were already filtered), but the data leaves the deployment, so the provider's terms must suit the documents. API keys are read from environment variables only, are never logged and never appear in error messages (`tests/test_llm_providers.py`).

## 7. What an independent review should check

1. Whether the SQL filter in `vector_store.secure_hybrid_rrf_search` can be bypassed by any other code path that
   reads `parent_chunks` or `child_chunks` (search for direct reads outside that function and the admin services).
2. The upload path end to end with files designed to evade the content scan and the reviewer model.
3. SSO against a real provider, including account binding and what happens when a provider subject changes.
4. Behaviour under concurrent use across several server processes (rate limit and lockout are per process).
5. Whether prompts and models used in production resist planted instructions better than the local 7B model.

Everything in sections 4 and 5 can be re-run: `python -m scripts.verify_access`, `python -m scripts.security_probe`,
`python -m pytest -q tests`.
