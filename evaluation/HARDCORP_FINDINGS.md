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
