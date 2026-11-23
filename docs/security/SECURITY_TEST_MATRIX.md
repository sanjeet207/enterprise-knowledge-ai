# Security test matrix

Each row is an attack, what must happen, and the check that proves it. Three kinds of check:

- **Unit test**: `pytest tests/` (no server needed).
- **Probe**: `python -m scripts.security_probe` (live server; tokens, other companies, uploads, planted instructions).
- **Matrix run**: `python -m scripts.security_matrix --report evaluation/SECURITY_MATRIX_RESULTS.md` (live server; access changed
  while a person is signed in, restricted titles, the research assistant, attempts to widen access). Row ids M1 to M14, plus the controls M1a, M4a, M5a and M13a, which prove a check is not passing trivially.

The results of the latest matrix run are written to `evaluation/SECURITY_MATRIX_RESULTS.md`. A row that failed or surprised us
is written down there and in "Findings" below, not hidden.

| # | Attack | Must happen | Proven by |
|---|---|---|---|
| 1 | Ask for another company's document (read, compare, delete) | 404, identical to a missing document | Probe "Other companies and other people"; `verify_access.py` (company checks); matrix M14 for reports |
| 2 | Ask about a restricted document (level or engagement team) | Not found in search or answers; the refusal names nothing | `verify_access.py` 9/9; evaluation "Restricted" 100% (14/14 and 9/9); matrix M8, M9 |
| 3 | Research assistant asked for restricted material | Report cites nothing the person may not read; reports are private to their author | Same retriever and filters as chat; matrix M13, M14 |
| 4 | Read, continue, rate or delete someone else's conversation | 404 | Probe "Other people" |
| 5 | Keep reading a restricted document after the person lost access | The next request already refuses (access is read from the database on every request, not from the token) | Matrix M1 (level lowered), M3 (account switched off), M4 (team membership removed) |
| 6 | A pending request for access is treated as access | It is only a record; nothing is widened until an administrator changes the person's level or team | Matrix M2; `tests/test_access_requests.py` |
| 7 | Old chat history shows restricted material after access was lost | On loading, an answer built on a document the person can no longer open is replaced by a notice and its sources are emptied; their own questions stay (see Findings) | Matrix M5a, M5; `tests/test_conversation_access.py` |
| 8 | Restricted titles or metadata leak through lists, search or errors | None shown | Matrix M6 (no list for analysts), M7 (managers see only their own uploads), M8, M9 |
| 9 | A document contains instructions aimed at the AI | Treated as data: refused at upload, held for review, or ignored | Probe "Instructions planted in documents"; `test_security_hardening.py`; `check_inspector.py` |
| 10 | Delete a document without the right | Denied, and the document is still there | Probe (analyst, other company); matrix M10 |
| 11 | Raise your own level, or an administrator grants level 4 | Denied | Probe "Role escalation"; `admin_policy` unit tests; matrix M11 |
| 12 | Use administration or audit functions without the role | 403 | Probe; matrix M12 |
| 13 | Forged, unsigned, swapped or wrong-secret tokens | 401 | Probe "Tokens" |
| 14 | Malicious uploads (zip bomb, fake PDF, program, oversized) | Refused | Probe "Malicious uploads"; `test_upload_policy.py` |
| 15 | Stolen single sign-on response, replayed or forged | Refused (state, nonce, signature, audience, expiry) | `tests/test_oidc.py` |
| 16 | A directory group is removed from a person | Access follows the directory at the next sign-in; no mapped group means no sign-in | `tests/test_sso_groups.py` |

## What the matrix does not show

- It is a set of attacks we thought of, written as repeatable checks. It is not a penetration test.
- Rows 15 and 16 are proven with fake tokens and fake accounts, not against a real Entra tenant.
- Single-sign-on group removal takes effect at the person's next sign-in, not instantly (see `docs/SSO.md`).
- Rate limiting and lockout state live in one process; a multi-instance deployment needs a shared store
  (see `docs/SECURITY_REVIEW.md`, known limits).

## Findings

First live run: 16 of 17 checks passed, one observation (M5), one failure that turned out to be a mistake in the check (M13). After the M5 fix and the added controls, the latest run passes 20 of 20.

- **M5, old conversations after access is lost (found, fixed):** conversations were saved with the answer and source
  titles shown at the time. A person removed from the Project Titan team could no longer search or ask for the memo
  (M4, M4b pass), but their earlier conversation still showed its title and the answer text built from it. Policy now:
  when a conversation is loaded, each cited document is checked against the person's current access (company,
  published, level, team, read from the database). If any cited document is no longer open to them, that answer is
  replaced by a notice and its sources are emptied. Their own questions, refusals and answers built only on documents
  they can still open are unchanged. The check applies to the chat screen and to the "export my data" download.
  Messages saved before this change carry only a title, so they are matched by title; if it cannot be matched they are
  hidden (fail closed). Saved research reports follow the same rule: a finding that cites a closed document is replaced by a notice, and because the summary and the flagged inconsistencies mix every finding they are removed; closed sources leave the source list (matrix M5c, M5r). Not covered: the audit log, which holds titles and document ids but no document text.
- **M13, research report (false alarm, check fixed):** the first run failed because the check searched the whole report for
  restricted titles, and the report repeats the request, which contained the words "executive compensation framework". The
  check now looks only at the documents the report cites and the text it wrote, not at the request. Lesson kept here
  because it is easy to make: a check that matches the person's own words proves nothing.
