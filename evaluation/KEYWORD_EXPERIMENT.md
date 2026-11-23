# Keyword search experiment

Only the keyword half changes: AND (every word must appear, today) against OR (any word may match, more matching words rank higher). Same access filter, same questions, no reranker.

## paraphrase questions (both sets) (49 questions)

| Variant | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | NDCG@10 | p50 ms | p95 ms | Not found |
|---|---|---|---|---|---|---|---|---|---|
| vector only | 88% | 98% | 100% | 100% | 0.933 | 0.950 | 21 | 26 | 0 |
| keyword AND (today) | 14% | 14% | 14% | 14% | 0.143 | 0.143 | 20 | 25 | 42 |
| keyword OR | 80% | 90% | 90% | 90% | 0.840 | 0.855 | 21 | 25 | 5 |
| hybrid, AND keyword (today) | 88% | 98% | 100% | 100% | 0.933 | 0.950 | 21 | 25 | 0 |
| hybrid, OR keyword | 86% | 98% | 100% | 100% | 0.910 | 0.933 | 21 | 23 | 0 |

Against today's hybrid search, question by question (better / worse / same rank):

- vector only: 0 better, 0 worse, 49 same
- keyword AND (today): 0 better, 42 worse, 7 same
- keyword OR: 6 better, 10 worse, 33 same
- hybrid, OR keyword: 5 better, 6 worse, 38 same

## exact-term searches (15 questions)

| Variant | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | NDCG@10 | p50 ms | p95 ms | Not found |
|---|---|---|---|---|---|---|---|---|---|
| vector only | 87% | 100% | 100% | 100% | 0.922 | 0.942 | 20 | 339 | 0 |
| keyword AND (today) | 93% | 93% | 93% | 93% | 0.933 | 0.933 | 20 | 22 | 1 |
| keyword OR | 100% | 100% | 100% | 100% | 1.000 | 1.000 | 19 | 20 | 0 |
| hybrid, AND keyword (today) | 100% | 100% | 100% | 100% | 1.000 | 1.000 | 19 | 21 | 0 |
| hybrid, OR keyword | 100% | 100% | 100% | 100% | 1.000 | 1.000 | 20 | 22 | 0 |

Against today's hybrid search, question by question (better / worse / same rank):

- vector only: 0 better, 2 worse, 13 same
- keyword AND (today): 0 better, 1 worse, 14 same
- keyword OR: 0 better, 0 worse, 15 same
- hybrid, OR keyword: 0 better, 0 worse, 15 same

## How to read this

- The demo company has 14 short documents, so even meaning search alone finds almost everything. A real company has thousands of long ones, where exact words (policy numbers, names, codes) matter more. These numbers show the direction, not the size of the effect.
- Fifteen exact-term questions: one question is about 7 points. Treat a difference of one or two as noise.
