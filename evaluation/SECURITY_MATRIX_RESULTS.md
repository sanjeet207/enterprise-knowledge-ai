# Security matrix: latest live run (2026-11-23 07:25 UTC)

| Row | Attack | Result | Detail |
|---|---|---|---|
| M1a | Before: a level 2 person finds the level 2 document | PASS |  |
| M1c | Before: the saved conversation shows the level 2 answer and its source | PASS |  |
| M1d | Level lowered: the saved conversation now hides that answer and its source | PASS |  |
| M1 | Level lowered mid-session: the SAME token no longer finds it in search | PASS |  |
| M1b | ...nor in a chat answer | PASS | refused |
| M2 | A pending access request does not widen what the person can read | PASS | 201 |
| M3 | Account switched off mid-session: the SAME token is refused on the next request | PASS |  |
| M4a | Before: a team member finds the deal memo | PASS |  |
| M5c | Before: the team member's saved research report cites the deal memo | PASS |  |
| M5a | Before: the saved conversation shows the answer and its source to the team member | PASS |  |
| M4 | Removed from the team mid-session: the SAME token no longer finds the memo | PASS |  |
| M4b | ...nor in a new chat answer | PASS | refused |
| M5 | Old conversation after losing access: restricted answer and source title are hidden | PASS | answer replaced by a notice |
| M5r | Saved research report after losing access: restricted findings, summary and source title are hidden | PASS |  |
| M6 | An analyst gets no document list at all | PASS |  |
| M7 | A manager's document list holds only their own uploads, no restricted titles | PASS |  |
| M8 | Search for restricted topics returns no restricted title or text to an analyst | PASS |  |
| M9 | A refused answer lists no sources and names no restricted document | PASS | refused |
| M10 | A manager cannot delete a restricted document, and it is still there afterwards | PASS |  |
| M11 | A manager cannot raise their own level | PASS |  |
| M12 | A manager cannot create teams, add members or read the audit log | PASS |  |
| M15 | Only an administrator approves a pending document (manager, analyst and the uploader get 403) | PASS | [403, 403, 403], admin 200 |
| M16 | Version history: visible to the team member, 404 for an outsider, another company, and a missing id alike | PASS | {'owner': 200, 'analyst': 404, 'globex': 404, 'missing': 404} |
| M17 | Compare: works for the team member, 404 for an outsider, another company, and a missing id alike | PASS | {'owner': 200, 'analyst': 404, 'globex': 404, 'missing': 404} |
| M18 | Upload jobs: seen by the uploader and an administrator, not by another manager or another company | PASS | {'owner': 200, 'admin': 200, 'manager': 404, 'globex': 404} {'owner': True, 'manager': False, 'globex': False} |
| M19 | Uploading the same text as a level 3 document refuses it but does not name that document | PASS | 409 |
| M19a | Control: duplicating a document the uploader can read does name it | PASS | 409 |
| M20 | An uploader removed from the team can no longer delete their own document, and it is still there | PASS | 404 |
| M20a | Control: while still on the team the uploader can delete their own document | PASS | 200 |
| M21 | Another person cannot delete someone's conversation, and it is still there | PASS |  |
| M22 | Another person cannot rate someone's answer (404); the owner can (control) | PASS |  |
| M13 | A research report by an analyst cites no restricted document | PASS | 0 sources cited |
| M13a | Control: on an allowed topic the same assistant does cite documents (so M13 is not passing by citing nothing) | PASS | 2 sources cited |
| M14 | Another person cannot read that report, nor another company | PASS |  |
