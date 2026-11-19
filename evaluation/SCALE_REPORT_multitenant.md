# Scale test (with 30,000 documents of other tenants in the same tables)

Machine: macOS-26.7.3-arm64-arm-64bit, Python 3.12.2. Synthetic corpus in its own tenant; retrieval only, no answer model.
Needles are unique facts hidden among noise documents that look like them; 30% of the noise is restricted (level 4). A level-1 user is also asked about restricted needles: finding one is a leak, and recall counts only the questions that user may see.

| Documents (this tenant) | Chunks (this tenant) | Insert (docs/s) | Search p50 / p95 (ms) | Query embed p50 (ms) | Right document in top 5 | Mean results returned | Restricted leaks | Table size (MB) |
|---|---|---|---|---|---|---|---|---|
| 1,000 | 2,955 | 88 | 30 / 37 | 11 | 100% | 5.0 | 0 | 673.3 |

Level-4 user searching for the restricted needles (should find them):

| Documents | Right document in top 5 | Search p50 (ms) |
|---|---|---|
| 1,000 | 100% | 35 |

Simultaneous searches (level-1 user):

| Documents | Workers | Searches/s | p50 / p95 (ms) | Errors |
|---|---|---|---|---|
| 1,000 | 1 | 30.4 | 32 / 44 | 0 |
| 1,000 | 4 | 75.9 | 52 / 63 | 0 |
| 1,000 | 8 | 93.1 | 85 / 106 | 0 |

Recall below 100% or a mean result count below 5 at larger sizes means the access filter leaves the vector search with too few candidates (filtered approximate search), not that a model is wrong.
