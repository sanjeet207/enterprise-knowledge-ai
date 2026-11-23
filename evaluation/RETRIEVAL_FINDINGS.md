# Retrieval ablation: what the numbers say

Numbers come from `evaluation/RETRIEVAL_ABLATION.md` (regenerate with `python -m scripts.retrieval_ablation`). This file is hand-written, so a re-run does not overwrite it. 49 answerable questions (37 + 12), one right document each, MiniLM-L6 embeddings. With this few questions, one question is 2 points: treat gaps under about 5 points as noise.

## Findings

1. **Hybrid search is identical to vector-only on this question set.** 0 better, 0 worse, 49 the same. The keyword half adds nothing here.
2. **The keyword half is weak on natural-language questions, and the cause is known.** Alone it reaches 14% recall (42 of 49 questions find nothing). The query uses `plainto_tsquery`, which requires every word of the question to appear in one chunk (the plan shows `'allow' & 'legal' & 'depart'`). A question with one word the document never uses matches nothing. It works when the question holds an exact term (see the scale test: "Tormelket0"), which this question set, written in everyday paraphrase, does not test.
3. **The reranker alone is not clearly better.** By its own order it moves 5 questions up and 4 down, and recall@5 drops from 100% to 94%.
4. **Fusing the reranker with the search order is the best variant**: recall@1 88% to 92%, recall@5 100%, MRR 0.933 to 0.945 (5 up, 3 down). This is why it is the default. The gain is real in direction but small: 2 questions at rank 1.
5. **Cost of the reranker:** median retrieval time about 19 ms to 63 ms. Small next to answer generation (median 9 s), so the trade is acceptable, but it is a cost.
6. **Recall@10 is 100% for every variant except keyword-only.** The right document is always somewhere in the top 10; the question is only how high it ranks.

## What this does not show

- Not general enterprise accuracy: a small, clean corpus with one right document per question.
- Not the value of the keyword half for exact identifiers (policy numbers, codes, names). No question set here targets that.
- Not multi-document, conflicting-version or outdated-document questions.

## What I would do next

- Try `websearch_to_tsquery` or an OR-style query for the keyword half and re-run. Expect keyword-only to improve; the open question is whether hybrid then beats vector-only.
- Add about 15 questions that hinge on an exact term (codes, section numbers, names) so the keyword half is tested on what it is for.
- Grow the independent set (the existing plan) before drawing conclusions from any difference this small.
