# Retrieval ablation

Embedding: local / sentence-transformers/all-MiniLM-L6-v2. One right document per question; recall@k means the right document is within the first k passages. Latency is the whole retrieval step (query embedding, SQL, rerank).

## Northwind hard corpus (46 answerable questions)

| Variant | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | NDCG@10 | p50 ms | p95 ms | Not found |
|---|---|---|---|---|---|---|---|---|---|
| vector only | 67% | 100% | 100% | 100% | 0.837 | 0.880 | 31 | 320 | 0 |
| keyword only | 24% | 24% | 24% | 24% | 0.239 | 0.239 | 22 | 26 | 35 |
| hybrid (RRF) | 72% | 100% | 100% | 100% | 0.859 | 0.896 | 20 | 23 | 0 |
| hybrid + rerank (reranker order only) | 89% | 98% | 100% | 100% | 0.940 | 0.956 | 225 | 272 | 0 |
| hybrid + rerank (guarded) | 89% | 98% | 100% | 100% | 0.940 | 0.956 | 237 | 337 | 0 |
| hybrid + rerank, fused with search order (default) | 89% | 100% | 100% | 100% | 0.942 | 0.957 | 234 | 286 | 0 |

Against plain hybrid search, question by question (better / worse / same rank):

- vector only: 0 better, 2 worse, 44 same
- keyword only: 1 better, 35 worse, 10 same
- hybrid + rerank (reranker order only): 9 better, 2 worse, 35 same
- hybrid + rerank (guarded): 9 better, 2 worse, 35 same
- hybrid + rerank, fused with search order (default): 9 better, 2 worse, 35 same

By kind of question (recall@1 / recall@5; each cell is the number of questions of that kind):

| Kind | n | vector only | keyword only | hybrid (RRF) | hybrid + rerank (reranker order only) | hybrid + rerank (guarded) | hybrid + rerank, fused with search order (default) |
|---|---|---|---|---|---|---|---|
| current-version | 4 | 1/4 | 0/0 | 1/4 | 1/4 | 1/4 | 1/4 |
| exact-term | 10 | 8/10 | 9/9 | 10/10 | 10/10 | 10/10 | 10/10 |
| lookup | 24 | 19/24 | 2/2 | 19/24 | 23/24 | 23/24 | 23/24 |
| old-version | 2 | 0/2 | 0/0 | 0/2 | 1/2 | 1/2 | 1/2 |
| region | 6 | 3/6 | 0/0 | 3/6 | 6/6 | 6/6 | 6/6 |

## How to read this

- With about fifty questions, a difference of one or two questions is noise. Look for gaps that hold in both sets and across several columns.
- Parent-child retrieval (search small chunks, hand the model the whole section) is not a ranking choice and is not compared here. Query rewriting needs a model and is measured separately (see `evaluation/refiner_experiment`).
- Depth: the recall@1, 3, 5 and 10 columns are the top-K sweep. The application keeps 5 passages after reranking.
