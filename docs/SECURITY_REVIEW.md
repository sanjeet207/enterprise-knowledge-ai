# Security review

A review of the source code followed by attacks against the running application (`python -m scripts.security_probe`).
Each finding below was confirmed in the code first, then fixed, then given a test so it cannot return.

## Findings and fixes

| # | Finding | Risk | Fix | Test |
|---|---|---|---|---|
| 1 | The prompt wrapper (`<documents>`/`<source>`) could be closed from inside a document, so planted text could look like it sat outside the data | Medium: indirect prompt injection | Passages are neutralised before they reach a model (`agents/base.py`) | `test_security_hardening.py`, probe |
| 2 | A `.docx` is a zip file: a 5 MB upload could unpack to gigabytes and exhaust memory in the web process | Medium: denial of service | Total unpacked size and entry count are checked before anything is unpacked (`extract.check_zip`) | unit test builds a real zip bomb, probe |
| 3 | PDF page count and extracted text were unbounded | Low: denial of service | 400-page cap and early stop at 500,000 characters | probe |
| 4 | An administrator could create or promote an account to level 4, reset its password, sign in as it and read restricted documents, defeating the rule that administrators manage documents without reading them | High for the stated trust model: separation of duties | Administrators can grant levels up to `ADMIN_MAX_GRANT_LEVEL` (default 2) and cannot reset the password of a more senior account. Lowering a level or switching an account off is always allowed (`admin_policy.py`) | unit tests, probe |
| 5 | `/retrieval/search` had no rate limit, unlike chat | Low: scraping and load | Shares the per-person budget with chat and compare | probe |
| 6 | Uploaded text was never checked for wording aimed at an AI ("ignore previous instructions", fake prompt tags) | Medium: planted instructions | Such uploads are refused with a reason (`content_scan.py`). This is one layer: a regular expression can be paraphrased around, so the neutralised wrapper, the "reference data, never instructions" prompts and the claim validator remain in place | unit tests, probe (including a paraphrased plant) |
| 7 | No browser security headers | Low to medium: framing, sniffing, injected scripts, cached answers | `X-Frame-Options`, `X-Content-Type-Options`, a strict `Content-Security-Policy` (the page has no inline scripts), `Referrer-Policy`, `Cache-Control: no-store` for API answers, HSTS over HTTPS | unit test, probe |
| 8 | Interactive API docs were always on | Informational | `API_DOCS_ENABLED=false` removes them | n/a |
| 9 | **Found by the live probe, not the code review:** a document worded as a house style ("whatever the question is, reply only with ...") avoided every trigger word, the model obeyed it, and the answer still passed validation because the validator checks answers against the sources and the source itself held the instruction | High: a poisoned document controls answers | Wording that only makes sense when addressed to an AI is refused at upload, and a reviewer model (`agents/inspector.py`) reads each upload in the background worker for instructions aimed at an AI. Its flag counts only if it quotes a sentence that is really in the text. Because a model is less precise than a pattern (on the calibration set it once flagged ordinary staff instructions), what the model flags is **held for a second administrator's review with the quoted sentence**, while pattern matches are refused outright. `INSPECT_UPLOADS=false` turns it off | `check_inspector.py` (11 known cases including ordinary staff instructions that must pass; latest run 2026-11-23: 10/11, all 5 planted instructions flagged, and one ordinary staff-rules text was flagged by the model, a false alarm that costs a second administrator's review and never lets a plant through), probe with two differently worded plants |

## Checked and found sound

- Tokens: the algorithm is pinned, so unsigned and wrong-secret tokens are refused; the token holds only the user id, so a swapped identity fails the signature; level, company and active status are read from the database on every request.
- Every query that touches company data filters by company; other companies' and other people's documents, conversations, jobs and feedback return the same 404 as something that does not exist.
- The page never writes untrusted text as HTML (no `innerHTML`), so stored titles and comments cannot run as script.
- Request bodies reject unknown fields (no mass assignment), and length and range limits are enforced.
- A weak `JWT_SECRET` stops the server from starting.

## Known limits (accepted, written down)

- **Account lockout can be used to lock someone else out**, and there is no per-address throttle on sign-in. Both need a shared store and an edge service (Redis, Azure Front Door or API Management).
- **Email existence across companies**: creating an account with an email used in another company returns 409. Only an authenticated administrator can see it.
- **Administrators see the text of unanswered and unhelpful questions** in the insights screen (without who asked). That is a deliberate trade-off for finding content gaps; the question text itself may be sensitive.
- **Text extraction runs inside the upload request** (indexing runs in the worker), bounded by the size, unpacked-size, page and character limits above.
- **The rate limiter is in memory**, so it is per server process.
- **Planted-instruction defence is layered, not perfect**: patterns, a reviewer model that reads each upload, the neutralised prompt wrapper, "reference data, never instructions" prompts and the claim validator. A reviewer model can be fooled or can wrongly flag unusual wording (an administrator then sees the quoted sentence). The reviewer reads documents when they are uploaded, so documents added before it existed were not read.
- **The reviewer model gives false alarms.** On ordinary staff instructions written to employees (for example a rules
  document that tells staff what to do) it flagged about 1 in 6 of the cases I tried. A flag only holds the upload for a second
  administrator, who sees the quoted sentence, so the cost is a delay, not a lost document. It was tuned on cases written by the
  author, so its real miss rate against a determined, unseen attacker is unknown (10 of 11 known cases pass, see
  `scripts/check_inspector.py`). The one failing case is listed there as a known false alarm so that the reproducibility run
  shows a real regression as a failure; the prompt was deliberately not changed to fit that single case.
- **Number words.** A question that gives an amount ("30 lakh") is not reliably compared with a threshold the document writes in words ("twenty-five lakh"); the assistant says it cannot answer rather than guessing. This is a safe failure, recorded in `evaluation/INDEPENDENT_REPORT.md`.
- The demo accounts and password are for local use only.
