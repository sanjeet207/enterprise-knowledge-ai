# Scale test

Machine: macOS-26.7.3-arm64-arm-64bit, Python 3.12.2. Synthetic corpus in its own tenant; retrieval only, no answer model.
Needles are unique facts hidden among noise documents that look like them; 30% of the noise is restricted (level 4). A level-1 user is also asked about restricted needles: finding one is a leak, and recall counts only the questions that user may see.

| Documents | Chunks | Insert (docs/s) | Search p50 / p95 (ms) | Query embed p50 (ms) | Right document in top 5 | Mean results returned | Restricted leaks | Table size (MB) |
|---|---|---|---|---|---|---|---|---|
| 100 | 255 | 151 | 19 / 26 | 8 | 100% | 5.0 | 0 | 8.9 |
| 1,000 | 2,955 | 169 | 24 / 40 | 8 | 100% | 5.0 | 0 | 15.3 |
| 10,000 | 29,955 | 124 | 61 / 70 | 8 | 100% | 5.0 | 0 | 141.9 |

Level-4 user searching for the restricted needles (should find them):

| Documents | Right document in top 5 | Search p50 (ms) |
|---|---|---|
| 100 | 100% | 18 |
| 1,000 | 100% | 27 |
| 10,000 | 100% | 29 |

Simultaneous searches (level-1 user):

| Documents | Workers | Searches/s | p50 / p95 (ms) | Errors |
|---|---|---|---|---|
| 100 | 1 | 50.0 | 19 / 24 | 0 |
| 100 | 4 | 86.7 | 45 / 55 | 0 |
| 100 | 8 | 102.6 | 78 / 91 | 0 |
| 1,000 | 1 | 37.8 | 24 / 31 | 0 |
| 1,000 | 4 | 71.7 | 55 / 70 | 0 |
| 1,000 | 8 | 86.6 | 90 / 109 | 0 |
| 10,000 | 1 | 30.9 | 29 / 60 | 0 |
| 10,000 | 4 | 70.1 | 56 / 69 | 0 |
| 10,000 | 8 | 82.9 | 92 / 125 | 0 |

Recall below 100% or a mean result count below 5 at larger sizes means the access filter leaves the vector search with too few candidates (filtered approximate search), not that a model is wrong.
