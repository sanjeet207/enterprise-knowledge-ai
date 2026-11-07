# Evaluation report

Model: ollama:qwen2.5:7b, refusal threshold 0.1
Questions: 86
Questions asked at once: 1

| Metric | Result |
|---|---|
| Answer accuracy (answerable) | 100% (37/37) |
| Citation accuracy (answerable) | 100% (37/37) |
| Refusal accuracy (restricted, off-topic, injection) | 100% (24/24) |
| **Access leaks** | **0** |
| Multi-part questions (every part answered and cited) | 100% (6/6) |
| Restricted | 100% (14/14) |
| Off topic | 100% (3/3) |
| Injection (refused) | 100% (7/7) |
| General knowledge (answered, labelled, no sources) | 100% (8/8) |
| No-answer guard (no invented facts) | 100% (8/8) |
| Injection hidden in a valid question (no leak) | 100% (3/3) |
| Median latency, answered | 7.2s |
| Median latency, refused | 2.5s |
