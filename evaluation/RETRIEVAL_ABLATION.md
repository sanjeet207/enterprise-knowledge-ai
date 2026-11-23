# Retrieval ablation

Embedding: local / sentence-transformers/all-MiniLM-L6-v2. One right document per question; recall@k means the right document is within the first k passages. Latency is the whole retrieval step (query embedding, SQL, rerank).

## 86-question set (37 answerable questions)

| Variant | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | NDCG@10 | p50 ms | p95 ms | Not found |
|---|---|---|---|---|---|---|---|---|---|
| vector only | 86% | 97% | 100% | 100% | 0.924 | 0.944 | 26 | 137 | 0 |
| keyword only | 16% | 16% | 16% | 16% | 0.162 | 0.162 | 19 | 22 | 31 |
| hybrid (RRF) | 86% | 97% | 100% | 100% | 0.924 | 0.944 | 18 | 20 | 0 |
| hybrid + rerank (reranker order only) | 89% | 92% | 92% | 100% | 0.915 | 0.934 | 62 | 69 | 0 |
| hybrid + rerank (guarded) | 89% | 92% | 92% | 100% | 0.915 | 0.934 | 63 | 72 | 0 |
| hybrid + rerank, fused with search order (default) | 89% | 95% | 100% | 100% | 0.927 | 0.945 | 64 | 75 | 0 |

Against plain hybrid search, question by question (better / worse / same rank):

- vector only: 0 better, 0 worse, 37 same
- keyword only: 0 better, 31 worse, 6 same
- hybrid + rerank (reranker order only): 4 better, 4 worse, 29 same
- hybrid + rerank (guarded): 4 better, 4 worse, 29 same
- hybrid + rerank, fused with search order (default): 4 better, 3 worse, 30 same

## 27-question set (12 answerable questions)

| Variant | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | NDCG@10 | p50 ms | p95 ms | Not found |
|---|---|---|---|---|---|---|---|---|---|
| vector only | 92% | 100% | 100% | 100% | 0.958 | 0.969 | 24 | 38 | 0 |
| keyword only | 8% | 8% | 8% | 8% | 0.083 | 0.083 | 19 | 22 | 11 |
| hybrid (RRF) | 92% | 100% | 100% | 100% | 0.958 | 0.969 | 19 | 20 | 0 |
| hybrid + rerank (reranker order only) | 100% | 100% | 100% | 100% | 1.000 | 1.000 | 56 | 72 | 0 |
| hybrid + rerank (guarded) | 100% | 100% | 100% | 100% | 1.000 | 1.000 | 54 | 70 | 0 |
| hybrid + rerank, fused with search order (default) | 100% | 100% | 100% | 100% | 1.000 | 1.000 | 56 | 72 | 0 |

Against plain hybrid search, question by question (better / worse / same rank):

- vector only: 0 better, 0 worse, 12 same
- keyword only: 0 better, 11 worse, 1 same
- hybrid + rerank (reranker order only): 1 better, 0 worse, 11 same
- hybrid + rerank (guarded): 1 better, 0 worse, 11 same
- hybrid + rerank, fused with search order (default): 1 better, 0 worse, 11 same

## both sets together (49 answerable questions)

| Variant | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | NDCG@10 | p50 ms | p95 ms | Not found |
|---|---|---|---|---|---|---|---|---|---|
| vector only | 88% | 98% | 100% | 100% | 0.933 | 0.950 | 26 | 139 | 0 |
| keyword only | 14% | 14% | 14% | 14% | 0.143 | 0.143 | 19 | 23 | 42 |
| hybrid (RRF) | 88% | 98% | 100% | 100% | 0.933 | 0.950 | 19 | 20 | 0 |
| hybrid + rerank (reranker order only) | 92% | 94% | 94% | 100% | 0.936 | 0.950 | 61 | 72 | 0 |
| hybrid + rerank (guarded) | 92% | 94% | 94% | 100% | 0.936 | 0.950 | 61 | 73 | 0 |
| hybrid + rerank, fused with search order (default) | 92% | 96% | 100% | 100% | 0.945 | 0.958 | 63 | 75 | 0 |

Against plain hybrid search, question by question (better / worse / same rank):

- vector only: 0 better, 0 worse, 49 same
- keyword only: 0 better, 42 worse, 7 same
- hybrid + rerank (reranker order only): 5 better, 4 worse, 40 same
- hybrid + rerank (guarded): 5 better, 4 worse, 40 same
- hybrid + rerank, fused with search order (default): 5 better, 3 worse, 41 same

## How to read this

- With about fifty questions, a difference of one or two questions is noise. Look for gaps that hold in both sets and across several columns.
- Parent-child retrieval (search small chunks, hand the model the whole section) is not a ranking choice and is not compared here. Query rewriting needs a model and is measured separately (see `evaluation/refiner_experiment`).
- Depth: the recall@1, 3, 5 and 10 columns are the top-K sweep. The application keeps 5 passages after reranking.
