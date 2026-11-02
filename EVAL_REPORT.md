# Evaluation report

Model: ollama:qwen2.5:7b, refusal threshold 0.1
Questions: 80
Questions asked at once: 1

| Metric | Result |
|---|---|
| Answer accuracy (answerable) | 100% (37/37) |
| Citation accuracy (answerable) | 100% (37/37) |
| Refusal accuracy (restricted, off-topic, injection) | 100% (26/26) |
| **Access leaks** | **0** |
| Multi-part questions (every part answered and cited) | 100% (6/6) |
| Restricted | 100% (14/14) |
| Off topic | 100% (5/5) |
| Injection (refused) | 100% (7/7) |
| No-answer guard (no invented facts) | 100% (8/8) |
| Injection hidden in a valid question (no leak) | 100% (3/3) |
| Median latency, answered | 6.8s |
| Median latency, refused | 2.4s |
