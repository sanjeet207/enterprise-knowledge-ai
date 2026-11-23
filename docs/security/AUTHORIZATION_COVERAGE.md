# Authorization coverage

Every route in `app/routers/`, read from the code on 2026-11-23, following each call into the service and its SQL.
"Test evidence" names only tests that exist. "None yet" means no automated test exercises that behaviour.

Shared rules: `get_current_user` decodes the JWT and loads the person from the database on every request, so level,
active status and team are never taken from the token. A deactivated person is refused with 401.
`require_admin` and `require_level(n)` sit on top of it.

## Reading content

| Route | Who can call | Tenant | Document-level check | Failure looks like | Test evidence |
|---|---|---|---|---|---|
| `POST /retrieval/search` | any signed-in person | SQL `tenant_id` | SQL: published, level <= person, team membership | fewer or no results | M1, M8 |
| `POST /chat/query`, `/chat/stream` | any signed-in person | same SQL | same; refused answers list no sources | refusal with no sources | M1b, M9, M4b |
| `GET /chat/conversations`, `/{id}` | owner only (`user_id`) | via owner | owner, then every cited document is re-checked now | 404 for someone else's; hidden-answer notice after access loss | M5, M5a, M1c, M1d, `test_conversation_access.py` |
| `DELETE /chat/conversations/{id}`, `POST /chat/messages/{id}/feedback` | owner only | via owner | not content | 404 | M21, M22 |
| `POST/GET/DELETE /research...` | owner only | stored with report | cited documents re-checked on read | 404; hidden-finding notice | M5c, M5r, M13, M13a, M14, `test_report_access.py` |
| `GET /me/data` | the person themself | via owner | export applies the same re-check | n/a | same function as saved conversations and reports (unit-tested there); no test calls `/me/data` itself |
| `POST /documents/compare` | any signed-in person | SQL `tenant_id` | `readable_text`: level, team, status published/archived | 404 for missing and for not allowed (no difference) | M17 |
| `GET /documents/{id}/versions` | any signed-in person | `info()` tenant-scoped, then `history()` | history filtered by level and team; id must be in it | 404 for missing and for not allowed | M16 |

## Managing content

| Route | Who can call | Rule | Test evidence |
|---|---|---|---|
| `GET /documents` | admin (all, titles only) or level >= 2 (own uploads only) | others get 403 | M6, M7 |
| `DELETE /documents/{id}` | admin, or the uploader while they can still read the document | 404 otherwise, same as a missing id | M10, M20, M20a, `test_upload_policy.py` |
| `POST /documents/upload`, `/ingest` | admin; level >= 2 into a team they belong to, not above their own level | `upload_policy.check_upload`, re-run by the worker | `test_upload_policy.py`, `test_job_policy.py` |
| New version via `new_version_of` | admin or uploader; level and team are inherited, so versioning cannot lower protection; then the normal upload check is re-run | 404 or 403 | `test_upload_policy.py` |
| `GET /documents/jobs`, `/jobs/{id}` | admin sees the company's jobs, everyone else their own; `job_id` of someone else's gives 404 | tenant and owner in code | M18 |
| `POST /admin/documents/{id}/approve` | admin, not the uploader | 403 for non-admins, 409 for own upload | M15 (403 for manager, analyst, uploader) |
| `/admin/users`, `/teams`, `/events`, `/insights` | admin only; every query takes `tenant_id` | 403 | M11, M12 |
| `/audit/events`, `/audit/export.csv` | level 4 only, own tenant | 403 | M12 |
| `/access-requests` | own requests; admin queue is tenant-scoped, and an admin cannot decide their own | 403, 404 | `test_access_requests.py`, M2 |

## Gaps found by this inspection

1. **Fixed, tested: duplicate-content error leaked a title.** Uploading content identical to an existing document
   named it whatever its level or team. Now the title is shown only if the uploader may read it
   (`ingest.duplicate_message`; `tests/test_duplicate_disclosure.py`; live M19, M19a).
   Residual: the message still confirms that the content exists. An attacker needs the exact text, so this is a
   confirmation oracle, not a way to discover documents.
2. **Fixed: routes had no tests.** `/compare`, `/versions`, `/jobs`, `/jobs/{id}`, `/approve`, conversation delete and
   feedback now have live checks (M15 to M22), all passing in the 2026-11-23 run (34/34).
3. **Decided and fixed: deletion follows current access.** An uploader could delete their own document after being
   removed from its team. Now an uploader needs current read access (level and team) to delete or re-version it;
   administrators are unchanged. Deletions are audited (`document.delete`). Tests: `test_upload_policy.py`, M20, M20a.
   Residual: an administrator can still delete any document, by design.
4. **Archived versions are readable** through `/compare` and `/versions` under the same level and team rules. That is
   intended (version history). It differs from saved answers, which are hidden when any cited document was replaced.
5. **Admin metadata:** administrators see titles of all documents and jobs, including ones above their reading level.
   Content is never returned. This is the documented separation of managing from reading.
6. **Still untested:** `/me/data` and `/me/erase` are not called by any test; `/access-requests` is covered by unit
   tests only; the SSO routes are covered by unit tests, not against a live identity provider.

## Not applicable (features do not exist)

Answer cache, document download, conversation sharing, conversation search.
