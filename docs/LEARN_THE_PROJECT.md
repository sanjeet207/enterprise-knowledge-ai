# Learn the project, from the idea to the details

A study guide. Each part says what the thing is, why it exists, and where it lives in the code. Facts marked (code) were
read in the source; facts marked (README) come from the README and results files.

## Part 1. The problem and the idea

A language model does not know your company's documents, and it will happily invent an answer. **RAG** (retrieval
augmented generation) fixes that in two steps: first *retrieve* the few passages that match the question, then ask the model
to *answer only from those passages*.

A basic RAG demo stops there. A company needs three more things, and they are what this project is about:
1. **Permissions.** An analyst must not get a partner-only document, even indirectly.
2. **Trust.** Every answer must show its sources, and an answer that cannot be checked must not be shown.
3. **Audit.** Every question and outcome must be recorded.

The central design choice: **security is enforced by the database query and by plain code, not by asking the model to behave.**
A model can be tricked; a query that never fetches the document cannot leak it.

## Part 2. The data (code: `app/services/vector_store.py`)

| Table | Holds |
|---|---|
| `users` | id, tenant, email, `role_level` 1 to 4 (analyst, manager, director, partner) |
| `engagements` | client projects or secure workspaces |
| `engagement_members` | who is on which engagement (need-to-know) |
| `parent_chunks` | passage text, tenant, `classification_level`, optional `engagement_id`, `status` (published or not) |
| `child_chunks` | small pieces of a parent, with the vector embedding and a keyword index |

**Hierarchical chunking** (code: `chunker.py`): a document is cut into **parents of 200 words**, each cut into **children of 50 words**.
Small children are searched (precise matching); the larger parent is what the model gets (enough context). There is no
overlap between chunks, so a fact that straddles a boundary can be split. That is a known trade-off worth being able to name.

**Embedding** (code: `config.py`): the model `all-MiniLM-L6-v2` turns text into a 384-number vector (`EMBEDDING_DIM`).
Texts with similar meaning get nearby vectors.

## Part 3. Finding the right passages (code: `SECURE_RRF_SQL`)

Two searches run inside one SQL statement, and their results are merged:
- **Vector search:** order children by distance to the question's vector (`<=>`, cosine). Good at meaning ("days off" finds "leave").
  An **HNSW index** makes this fast by approximating the nearest neighbours.
- **Keyword search:** PostgreSQL full-text search (`tsvector`, `plainto_tsquery`, `ts_rank`). Good at exact words and numbers.
- **Reciprocal Rank Fusion (RRF):** each result scores `1 / (k + rank)` in each list (k is 60), and the scores are added.
  It needs no tuning of score scales, because it only uses ranks.
- **Rerank** (README): a cross-encoder (FlashRank) reads question and passage together and re-scores the top results. Slower
  but more accurate than vectors alone.

**Why the order matters for security:** the query starts with an `allowed_parents` set (same tenant, published, clearance at
or below the user's level, and no engagement or one the user is a member of). Both searches are restricted to that set, so a
forbidden passage is never a candidate at all.

Known risk to measure: filtered approximate search can return fewer candidates than asked for when a user's allowed set is
small (the scale test is built to detect this; the `hnsw.iterative_scan` setting was not found in the code).

## Part 4. From passages to a checked answer (README: the Architecture section)

The **orchestrator is plain code**. It calls model "agents" for narrow jobs and decides everything that matters itself.

1. **Corrector** fixes typos; code rejects a fix that changes the meaning.
2. **Retriever** (Part 3). If the best rerank score is below `REFUSAL_THRESHOLD` (0.1), nothing relevant was found.
3. **Rewriter** tries up to 3 reworded searches when the first is weak.
4. **Question analysis** (code, no model) picks depth (quick, standard, deep) and answer shape (short, list, steps, comparison).
5. **Answerer** writes from the passages only, with `[n]` citations.
6. **Citation rule** (code): every factual sentence needs a citation.
7. **Validator** (model plus code): checks each claim against its source and that each citation points at a passage containing the sentence's words. A rejection goes back to the answerer with the reason, at most 2 retries.
8. **Outcomes:** `answered`, `refused`, `no_answer`, `unverified` (fail closed, nothing shown), `general` (optional), `error`.
9. **Audit:** every question is logged with outcome, sources, timings and the agent trace.

**Fail closed** means: when unsure, show nothing rather than a guess. That is why most misses on the hard sets are safe failures (`unverified` or `no_answer`) rather than wrong answers; the cost is that some correct answers are rejected too (see evaluation/HARDCORP_FINDINGS.md).

**Refusals reveal nothing:** "no results" and "not relevant" give the identical text, so a refusal cannot be used to learn that
a restricted document exists.

## Part 5. Who is asking (code: `app/security.py`)

- Passwords are stored as **bcrypt** hashes.
- Login returns a **JWT** that holds only the user id and an expiry (60 minutes).
- On **every request** the user is re-read from the database, so deactivation or a level change applies immediately.
- The token algorithm is pinned, so algorithm-switching attacks fail.
- Unknown email, wrong password, locked or disabled account all give the same answer, and a dummy hash check hides timing.
- **Lockout** (failed-login count stored in the `users` table, so it survives restarts and works across replicas) and the **question rate limit** (in memory, per process, so one replica only) slow guessing and abuse.
- **Admin is separate from reading level:** managing documents does not grant reading them.
- Optional **OIDC single sign-on** (README) with PKCE and token verification.

## Part 6. Measuring it (README, `evaluation/`)

- A question set is sent to the running API as real demo users, and each response is scored.
- Metrics: answer accuracy (right phrase present), citation accuracy (expected document cited), refusal accuracy,
  no-answer guard (no invented facts), multi-part completeness, and **leaks** (a forbidden fact in an answer; must be 0).
- Results (local model, all with 0 leaks): 86-question suite 37/37 answerable; 27-question set 11/12; Northwind development set 78% (36/46). Hosted Groq model on the 27-question set: 7/12, 10/12, then 12/12 across three runs. Also: 160 access checks, 34 live security-matrix checks, 57 attack-probe checks, 459 unit tests.
- **Why independent questions matter:** you wrote (or an AI wrote) these questions, so they match how you think. A stranger's
  questions test whether the system works outside your assumptions.
- `scripts/check_results.py` recomputes published numbers from the raw results so they cannot drift.

## Part 7. Running it anywhere (code: `app/services/llm.py`)

One setting, `LLM_PROVIDER`, chooses where the model runs: local **Ollama** by default, or **Anthropic**, **Groq** or any
OpenAI-compatible endpoint. Only `llm.py` knows about providers, so checks and access control are identical. Local model
names are never sent to a hosted provider. With a hosted provider, questions and passages leave your environment.

Operations drills that were run locally (docs/OPERATIONS.md): backup and restore into a scratch database, and a model-outage drill. Diagrams: docs/ARCHITECTURE.md.

Deployment path (docs/DEPLOY_AZURE.md, not yet run): container image, Azure Container Apps (one replica), PostgreSQL Flexible
Server with the `vector` extension, secrets for keys.

## Part 8. Questions you should be able to answer

1. Why filter in SQL instead of the prompt?
2. Why hybrid search instead of vectors alone?
3. What does RRF do, and why does it need no score tuning?
4. Why small child chunks but large parent passages?
5. What does "fail closed" mean here, and what does it cost?
6. How does a refusal avoid revealing that a document exists?
7. What would break if you ran two replicas?
8. Which parts of the evidence are weakest, and what would fix them?
