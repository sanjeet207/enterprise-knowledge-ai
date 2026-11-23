# Security matrix: latest live run (2026-11-23 06:48 UTC)

| Row | Attack | Result | Detail |
|---|---|---|---|
| M1a | Before: a level 2 person finds the level 2 document | PASS |  |
| M1 | Level lowered mid-session: the SAME token no longer finds it in search | PASS |  |
| M1b | ...nor in a chat answer | PASS | refused |
| M2 | A pending access request does not widen what the person can read | PASS | 201 |
| M3 | Account switched off mid-session: the SAME token is refused on the next request | PASS |  |
| M4a | Before: a team member finds the deal memo | PASS |  |
| M5a | Before: the saved conversation shows the answer and its source to the team member | PASS |  |
| M4 | Removed from the team mid-session: the SAME token no longer finds the memo | PASS |  |
| M4b | ...nor in a new chat answer | PASS | refused |
| M5 | Old conversation after losing access: restricted answer and source title are hidden | PASS | answer replaced by a notice |
| M6 | An analyst gets no document list at all | PASS |  |
| M7 | A manager's document list holds only their own uploads, no restricted titles | PASS |  |
| M8 | Search for restricted topics returns no restricted title or text to an analyst | PASS |  |
| M9 | A refused answer lists no sources and names no restricted document | PASS | refused |
| M10 | A manager cannot delete a restricted document, and it is still there afterwards | PASS |  |
| M11 | A manager cannot raise their own level | PASS |  |
| M12 | A manager cannot create teams, add members or read the audit log | PASS |  |
| M13 | A research report by an analyst cites no restricted document | PASS | 0 sources cited |
| M13a | Control: on an allowed topic the same assistant does cite documents (so M13 is not passing by citing nothing) | PASS | 2 sources cited |
| M14 | Another person cannot read that report, nor another company | PASS |  |
