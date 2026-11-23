# Interview notes

A guide for explaining this project in an interview. Every number comes from a report in `evaluation/` or a run recorded in
`docs/`; where something was not measured, it says so. Re-check the numbers against the repository before an interview: they
change when the code does.

## 30-second pitch

An internal "company brain". Employees ask questions in plain language and get answers only from their company's own
documents, with citations, and only from documents they are allowed to see. Access depends on clearance level and, for
sensitive material, on engagement-team membership. Off-topic questions are refused, answers are verified before they are
shown, and every question is written to an audit log. I built it to show I can make an AI system secure and measurable,
not just working.

## What I would point to

- **Access control is in the database query, not in the prompt.** Tenant, level and team are conditions of the SQL, so a
  document the person may not read is never fetched and the model cannot leak it. Evidence: 160 access checks against a real
  Postgres in CI; a live security matrix (34 attacks defended, including rights taken away mid-session on the same token); 57
  live attacks in the security probe; 0 leaks in every evaluation run.
- **Rights are read on every request.** The token carries only the user id, so lowering a level or switching off an account
  applies immediately. Saved conversations and research reports are re-checked when read.
- **Answers are checked, not trusted.** Relevance gate, a citation on every factual sentence (plain code), a claim validator
  with bounded retries, and "unverified" (nothing shown) when it cannot be confirmed.
- **The orchestrator is plain code.** Permissions, retry limits and the audit record are never given to a model.
- **It is measured, and the weak spots are written down.**

| Set | Result (local `qwen2.5:7b`) | Note |
|---|---|---|
| 86 questions | 37/37 answerable, 24/24 refused, 0 leaks | written by me against the same documents: a regression check, not proof |
| 27 questions | 11/12 answerable, 0 leaks | written by an AI assistant before results were seen; not independent of the project |
| Northwind, 67 questions | 78% (36/46) answerable, 0 leaks | messier company (versions, contradictions); a development set I tuned against |

  Hosted model (Groq free tier, `gpt-oss-120b`) on the 27-question set: 7/12, 10/12, then 12/12 across three runs. Treat it as
  roughly 80-100% on 12 questions, not a stable 100%. The 86-question and Northwind sets have not been run on it.
- **The model is a setting.** Local Ollama by default; Groq, Anthropic or any OpenAI-compatible endpoint by environment
  variable. 459 unit tests, with the provider code tested against a faked HTTP layer.
- **Operations drills were run, not just written.** Backup and restore into a scratch database (same row counts and index
  count), and a model outage drill (9/9: sign-in and search keep working, a question gets a plain 503 in about 3 s).

## Honest limits (say these before they are asked)

- **Not deployed.** The Azure runbook is written; nothing has run on a subscription. Single sign-on is implemented and
  unit-tested but has not been tried against a live Entra tenant.
- **No independent evaluation or security review.** Every question set was written by me or by the AI assistant that
  helped build the project. The security numbers are a self-assessment.
- **Northwind is a development set.** I changed the pipeline while looking at it, so 78% is not a clean measure.
- **Hosted providers see the question and the retrieved passages.** Data leaves the deployment.
- **Hosted-model accuracy is thin** (12 questions) and the free tier limits it to 30 requests a minute and 200,000 tokens a
  day per model.
- **Load on the answer path is unmeasured.** Retrieval was tested to 10,000 documents (median 61 ms, 8 concurrent searches);
  model answers were not load-tested. The rate limiter is in memory, so one replica only.
- **Backup drill compares row counts only**; it does not run a search on the restored copy, and restoring into the live
  database was not rehearsed.

## Likely questions, with real answers

1. *Why filter in SQL instead of telling the model what it may see?* A prompt is advice; a query is enforcement. If the
   passage never reaches the model, no injection can extract it.
2. *Why is the orchestrator not an agent?* Retry limits, permissions and the audit trail must be predictable and testable.
   Agents decide inside fixed tools and limits. I built a planner agent, measured it on/off, found no gain (4/6 both ways,
   about 2 s slower), and left it off.
3. *How do you know it is correct?* Four question sets with named misses, a validator on every answer, and checks that
   recompute published numbers from raw results. I do not claim more than a development-set result.
4. *Why hybrid search plus a reranker?* On the messy Northwind corpus the right document was first for 72% of questions with
   hybrid search and 89% with the reranker (it helped most on near-duplicate policies, such as the same leave policy for three
   countries). On the small demo the variants barely differed. The cost: retrieval went from about 20 ms to about 230 ms.
5. *What did you find by testing, not by reading code?*
   - The hosted model wrote citations as `【1】`; the pipeline did not recognise them and accuracy read 58%. After the fix it was
     83%, then 100% on the answerable questions in a later run.
   - A research report cited a restricted document in one matrix run (M13). Fixed, and a control was added so the check
     cannot pass by citing nothing.
   - Saved conversations still showed a restricted answer after access was removed (M5). Fixed for conversations and reports.
   - A source file with permission 600 crashed the non-root container on start. Fixed in the Dockerfile.
   - Adding document titles to every passage fixed "which version" questions but cost one question elsewhere; I restricted it
     to version pairs and recorded all three configurations.
6. *What is still weak?* Questions about the current versus an old version of a policy (the 2025 policy is first for only
   1 of 4 "current rule" questions), the validator rejecting some correct answers that carry figures from several versions, and
   short keyword-only questions.
7. *What would you do next?* Run the live Entra sign-in and a public smoke test on Azure, get a human outside the project to
   write a question set, run the 86 and Northwind sets on the hosted model, and move the rate limiter to Redis before more
   than one replica.
8. *What if the free hosted model disappears or is rate-limited?* The app waits as long as the provider asks (up to 30 s),
   retries up to three times, then returns a plain 503; sign-in and search still work, and the provider is one setting.
