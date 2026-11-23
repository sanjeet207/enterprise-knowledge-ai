# Hard corpus: retrieval findings (Northwind Capital)

Run of 2026-11-23, `python -m scripts.retrieval_ablation --hard`, on the fictional company in `scripts/hardcorp_data.py`:
31 documents, about 8,500 words, 183 passages, local embeddings (all-MiniLM-L6-v2). The corpus is built to be hard: long documents with
shared boilerplate, the same leave policy for three countries, two versions of the travel policy that both stay published, a stale
FAQ, two documents that disagree, and codes and form numbers asked as bare searches. Full tables: `RETRIEVAL_ABLATION_HARD.md`.

## Result (46 answerable questions, one right document each)

| Variant | Recall@1 | Recall@3 | Recall@5 | MRR | p50 ms |
|---|---|---|---|---|---|
| vector only | 67% | 100% | 100% | 0.837 | 31 |
| keyword only (all words must match) | 24% | 24% | 24% | 0.239 | 22 |
| hybrid (RRF) | 72% | 100% | 100% | 0.859 | 20 |
| hybrid + rerank (default, fused with search order) | 89% | 100% | 100% | 0.942 | 234 |

## What the numbers say

- **On the 14-document demo company the variants barely differed; here they do.** Hybrid search puts the right document first for 72% of
  questions; the reranker raises that to 89%. Against plain hybrid it ranks 9 questions better and 2 worse (35 the same). On the demo
  sets the same step moved 88% to 92%. The two question sets differ, so this is a direction, not a like-for-like comparison.
- **The right document is always within the first three.** Recall@3 is 100% for hybrid and for the default. The remaining mistakes are
  about order at rank 1, and the application hands the model 5 passages.
- **The reranker earns its cost on near-duplicates.** Leave-policy questions (same policy for India, the UK and Singapore): 3 of 6 first
  with plain hybrid, 6 of 6 with the reranker. Everyday-wording lookups: 19 of 24 first, then 23 of 24.
- **The reranker costs time.** Median retrieval goes from 20 ms to 234 ms per question on this corpus (p95 286 ms).
- **Exact terms are already solved by hybrid.** Codes and form numbers asked as bare searches (PR-7, VaultPlus, IR-HIGH-3): 10 of 10
  first with hybrid. Keyword alone is poor on everyday questions (35 of 46 not found) because every word must match.
- **Versions are the open weakness.** For questions about the *current* travel rule, only 1 of 4 puts the 2025 policy first under any
  variant, although all 4 are within the first five. For questions about the *old* 2023 rule: 0 of 2 first with hybrid, 1 of 2 with the
  reranker. Both versions stay published and nothing tells the search which one is current, so ranking falls back on wording. The
  likeliest cause is that the 2023 policy outranks the 2025 one on these questions; this run does not show which document came first,
  so check that before changing anything.

## Limits of this evidence

- 46 questions: one question is about 2 points. The version result rests on 4 and 2 questions.
- The corpus and the questions were written by the AI assistant that helped build the project, not by an outside person.
- One run, local embeddings, one machine. Latency is retrieval only, with no answer model.
- This measures finding the right document. Whether the answer is correct and cited is measured separately by the full-pipeline run
  (`python -m scripts.evaluate --eval-set evaluation/hardcorp_set.json --tag hardcorp`).

## Full pipeline on the same corpus (run of 2026-11-23, qwen2.5:7b via Ollama, refusal threshold 0.1)

All 67 questions asked through the running application, as the user each names (`python -m scripts.evaluate --eval-set
evaluation/hardcorp_set.json --tag hardcorp`; report `HARDCORP_REPORT.md`, answers `hardcorp_results.json`). 0 model errors.

| Metric | Result |
|---|---|
| Answer accuracy (answerable) | 70% (32/46) |
| Citation accuracy (answerable) | 72% (33/46) |
| Multi-part questions (every part answered and cited) | 50% (4/8) |
| Restricted questions refused | 6/6 |
| Questions with no document answer: no invented facts | 6/6 |
| Off-topic refused | 1/1 |
| **Access leaks** | **0** |
| Median latency, answered / refused | 17.6 s / 5.3 s |

### What the 18 failures look like

17 of the 18 failures are the system declining to answer; none shows a wrong answer. The outcome tells which stage stopped it:

| Outcome | Count | Questions |
|---|---|---|
| refused (best passage scored below the 0.1 gate) | 3 | hotel limit in Mumbai (answered "not related to your company"), when to change a password, stolen laptop |
| no_answer (the model said the documents do not contain enough) | 5 | taxi receipt, pasting client data into ChatGPT, the bare terms "MLRO" and "NorthTrip", UK leave plus working abroad |
| unverified (an answer was drafted but not shown) | 9 | four of the six version questions (current deadline, director approval, meal allowance, old hotel limit), client dinner, UK maternity leave, both ambiguous leave questions, the conflict question |
| answered, scored as a miss | 1 | "which function has the lowest attrition": the answer "The compliance function has the lowest attrition, with a rate of 5.1 percent [1]" is correct; the expected phrase was "compliance at 5.1", which is too rigid. This is a flaw in the question set, not in the system. |

### What this says

- **Safety held on the hard corpus**: no leaks, every restricted question refused, no invented facts on questions the documents do not cover.
- **Usefulness is the weak side**: about 70% of answerable questions get a correct, cited answer; the system prefers silence to a doubtful answer. That is the intended trade, but 3 of the 18 refusals happen at the relevance gate even though search had put the right document first to third. The gate threshold was chosen on the 14-document demo company; on long documents the best passage scores lower. A threshold sweep (`scripts/threshold_sweep.py`) is the next measurement.
- **Retrieval is not the bottleneck**: recall@3 was 100%. The losses come after retrieval: the relevance gate, the 7B model on paraphrases and on questions that need several sources, and the answer verification step rejecting answers that mix an old and a new policy.
- **Versions, ambiguity and conflicts fail closed**: 7 of the 9 "unverified" outcomes are version, ambiguous or conflict questions, where the right behaviour is to name every variant or the newest one. The system declines instead. Better handling is a product change, not a tuning change.
- **Bare keywords are not questions**: "MLRO" and "NorthTrip" were found by search (10/10 exact-term at rank 1) but a lone term gives the model nothing to answer. Whether to count them as answer failures is a question-design choice; they are reported as scored.

### Caveats

- The question set and ground truth were written by the AI assistant that built the project; one scoring phrase (above) is known to be too strict.
- This set is now a development set: anything changed in response to it must be measured on a set the change was not made on.
- One run, one local model; results vary between runs because the model's output varies.

## Refusal gate: what the sweeps showed (2026-11-23, measured, nothing changed)

`scripts/threshold_sweep.py` and `scripts/signal_check.py` (outputs `THRESHOLD_SWEEP.md`, `SIGNAL_CHECK.md`) ask the application's own retriever for the best relevance of every question, before any model is involved.

- **Lowering the threshold does not help.** On Northwind, 9 of 54 should-answer questions score below 0.1; at 0.005 still 6 do, because the reranker scores several everyday-wording questions at about 0.000 although search ranks the right document first to third.
- **The reranker score also does not separate answerable from unanswerable questions**: some unsupported questions on the demo company score 0.99.
- **Correction to the table above:** on Northwind, all 13 should-refuse questions score below the gate, so the "no invented facts 6/6" result was produced by the gate alone. The answer and verification stages were not exercised by those questions on this corpus. They were on the demo company, where 7 of 32 should-refuse questions pass the gate.
- **A second signal (cosine similarity to the closest readable passage), OR-ed with the reranker, fits Northwind at a cutoff of 0.4** (2 of 54 blocked instead of 9, 0 of 13 should-refuse passing) **but does not transfer**: at the same cutoff the 27-question demo set lets 4 of 13 should-refuse questions through instead of 2, and the 86-question set rescues only 3 of 12. The right cutoff differs by corpus, so no fixed value was adopted. Typo questions are scored raw here, so the demo-set blocked counts are overstated.
- **Size of the prize:** only 3 of the 18 Northwind failures were refused at the gate. Nine were drafted and then rejected by verification, the larger bucket.

## Version 2 run (2026-11-23, same model and 67 questions; two changes made after reading the v1 failures)

Changes, both made while looking at this question set, so this set is a development set and the gain below is not an independent result:
1. Plain-code citation rules (`answer_check.py`): an uncited sentence right after a cited one takes that citation only if at least 60% of its content words are in the cited passage; a first sentence that only says the answer varies by place ("This depends on your location") with no figure is no longer flagged. Every other uncited sentence still fails.
2. Document title: each passage the answer model and the validator read now starts with `Document: <title>` (switch off with `SOURCE_TITLES=0`). Before, neither could tell the 2023 from the 2025 travel policy.
3. One scoring phrase fixed ("compliance at 5.1" to "5.1"); v1 re-scored with the fix is 72% (33/46), not 70%.

| Metric | v1 as run | v1 with the scorer fix | v2 |
|---|---|---|---|
| Answer accuracy (answerable) | 70% (32/46) | 72% (33/46) | **83% (38/46)** |
| Citation accuracy | 72% (33/46) | 72% (33/46) | 83% (38/46) |
| Multi-part questions | 50% (4/8) | 50% (4/8) | **88% (7/8)** |
| Restricted refused / no-answer guard / off-topic | 6/6, 6/6, 1/1 | same | 6/6, 6/6, 1/1 |
| **Access leaks** | 0 | 0 | **0** |
| Median latency, answered | 17.6 s | | 18.0 s |

Nine of the 18 v1 failures now pass (client dinner, travel claim deadline, director approval, latest meal allowance, MLRO, annual leave, carry-forward limit, the conflict of interest question, attrition via the scorer fix); nothing that passed in v1 failed in v2. Nine still fail:
- refused at the relevance gate: hotel limit in Mumbai, password change, stolen laptop (reranker score about 0; see the gate section above);
- the answer model said the documents do not contain it: taxi receipt, pasting client data into ChatGPT, the bare term NorthTrip, UK leave plus working abroad (the second half needs a separate search);
- drafted but rejected: UK maternity leave, old hotel limit (the title line did not fix the old-version question).

Answers read in full for quality: the conflict question now states both rules and which document says which; the version questions name the 2025 policy. One imprecise answer was scored as a pass: "The daily meal allowance for client entertainment is up to INR 4,000 per person" mixes two different allowances (1,500 daily meal, 4,000 client entertainment); the figure is right, the label is not.

Limits: one run on one local 7B model, whose output varies between runs; changes tuned on this set; the two demo question sets have to be re-run to show nothing else got worse (`regress86`, `regress27`).
