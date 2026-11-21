# Failure analysis: 45-question hard set

Source: `evaluation/newflow_hard_results.json` (one run, local model). 42 of 45 passed; the three failures are the
only ones analysed here. Nothing in this file has been tuned against: no code was changed because of it.

**What is measured vs. guessed.** The outcome, latency and answer text below come from the results file. The
"likely cause" lines are hypotheses, not findings; each one says how to confirm it. One run is not enough to call a
failure stable, so each case also lists the repeat test to run first.

## Summary

| # | Question (short) | Outcome | Time | Failure type | Safe? |
|---|---|---|---|---|---|
| 1 | Customer records on a personal Google Drive at home | `unverified` | 20.2 s | Answer rejected by the validator | Yes, nothing wrong shown |
| 2 | Working from my home country for a month | `unverified` | 26.4 s | Answer rejected by the validator | Yes, nothing wrong shown |
| 3 | Who signs off a contract worth 40 lakh rupees | `no_answer` | 3.7 s | Evidence judged insufficient | Yes, nothing wrong shown |

All three fail in the safe direction: the system declined instead of giving a wrong or unsupported answer, and there
were 0 access leaks in the run. That is a limit on usefulness, not on safety.

## Case 1 and 2: `unverified`

The pipeline produced a draft, then the claim-checking step rejected it and the retries did not produce one it accepted,
so it showed "I couldn't produce an answer that is backed by your documents".

- **Likely cause (unconfirmed):** the check is strict about a claim the passage supports only indirectly (a rule stated
  as "may not use personal cloud storage" vs. a question phrased as "can I use my Google Drive"; a 30-day limit
  vs. "a month").
- **To confirm:** run `python -m scripts.diagnose` on each question and read which claim was rejected and why.
- **Before any fix:** ask each question 5 times. If it passes sometimes, it is variance, not a systematic miss.
- **Possible direction, only if confirmed:** improve validator precision for paraphrases. It must be measured on the
  whole suite so that a looser check does not let unsupported claims through.

## Case 3: `no_answer`

Answered in 3.7 s, far faster than the others, so it probably stopped early on a relevance or evidence check rather than
after a full answer attempt.

- **Likely cause (unconfirmed):** the question uses an Indian-rupee unit ("40 lakh") while the policy states the
  threshold in another form, so retrieval or the sufficiency check did not connect them. The expected answer is
  "director".
- **To confirm:** run the retrieval-only evaluation (`scripts/retrieval_eval.py`) for this question and see whether the
  Vendor Selection and Procurement Policy appears in the top results. If it does not, it is a retrieval miss; if it
  does, it is the sufficiency check.
- **Possible direction, only if confirmed:** number-and-unit normalisation at query time, evaluated on all categories.

## Rules for fixing these

1. Do not tune until the hard set hits 100%. Three cases fitted to one run prove little.
2. Repeat each failing question several times first, to separate variance from a real miss.
3. Any change is judged on both sets (86 and 45) and on access leaks; it is kept only if nothing regresses.
4. These questions were written by the project author, so a fix to them still needs the independent question set to
   show it generalises.
