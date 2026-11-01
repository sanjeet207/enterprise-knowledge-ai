# Evaluation report

Model: ollama:qwen2.5:7b, refusal threshold 0.1
Questions: 68

| Metric | Result |
|---|---|
| Answer accuracy (answerable) | 100% (31/31) |
| Citation accuracy (answerable) | 100% (31/31) |
| Refusal accuracy (restricted, off-topic, injection) | 100% (26/26) |
| **Access leaks** | **0** |
| Restricted | 100% (14/14) |
| Off topic | 100% (5/5) |
| Injection (refused) | 100% (7/7) |
| No-answer guard (no invented facts) | 100% (8/8) |
| Injection hidden in a valid question (no leak) | 100% (3/3) |
| Median latency, answered | 2.2s |
| Median latency, refused | 1.5s |
