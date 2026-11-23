# Revocation test results

What happens to things a person created or saw earlier when their access is taken away later.
Results below are from a run on 2026-11-23: **436 unit tests passed, security matrix 24/24** (server restarted
after the last code change).

## Rule

Level, active status and team are read from the database on every request, never from the token. Saved material
is re-checked when it is loaded: if any document it cites is no longer open to the person, the answer or finding is
replaced by a notice. Stored rows are not changed, so restoring access restores the answer. A cited document
counts as closed when it is above the person's level, in a team they have left, in another company, no longer
published (including replaced by a newer version), or when the person has no open documents at all.
Older rows with only a title are matched by title; a source with neither id nor title is treated as closed.

## Results by scenario

| Scenario | What happens | Evidence |
|---|---|---|
| Level lowered, same token, search | no longer finds the document | matrix M1 |
| Level lowered, new chat question | refused | matrix M1b |
| Level lowered, saved conversation | before: answer and source shown; after: answer replaced by a notice, source hidden | matrix M1c, M1d |
| Account switched off | same token refused with 401 on the next request | matrix M3 |
| Removed from engagement team, search and new chat | no longer found, refused | matrix M4, M4b |
| Removed from team, saved conversation | restricted answer and source title hidden | matrix M5a (before), M5 (after) |
| Removed from team, saved research report | findings, summary and source title hidden | matrix M5c (before), M5r (after) |
| Pending access request | does not widen access | matrix M2 |
| One closed source among several | whole answer hidden | `test_one_closed_source_among_open_ones_hides_the_whole_answer`, `test_one_lost_source_among_five_hides_the_answer` |
| All sources closed | whole answer hidden | `test_all_sources_lost_hides_the_answer` |
| Document replaced by a newer version | answers built on the old version hidden | `test_a_document_replaced_by_a_newer_version_hides_answers_built_on_the_old_one` |
| No open documents at all (deactivated, moved company) | every sourced answer hidden; the person's own questions stay | `test_nothing_open_at_all_hides_every_sourced_answer_but_not_the_persons_own_words` |
| Older messages without a document id | matched by title, case-insensitive, fail closed | `test_older_messages_without_a_document_id_are_matched_by_title_ignoring_case`, `..._whose_title_is_not_open_is_hidden`, `test_a_source_with_no_title_and_no_id_fails_closed` |
| Id and title disagree | id wins | `test_the_document_id_wins_over_a_matching_title` |
| Stored data untouched | reload gives the same stored rows | `test_the_stored_messages_are_not_modified`, `test_the_stored_report_is_not_modified` |
| Research report: finding-level behaviour | only findings citing a closed source are replaced; summary and inconsistencies are removed because they mix findings | `tests/test_report_access.py` (9 tests) |
| Data export (`/me/data`) | uses the same re-check | same functions; **no test calls the endpoint** |

Test files: `tests/test_conversation_access.py` (15 tests), `tests/test_report_access.py` (9),
`scripts/security_matrix.py` (live, 24 checks).

## Not applicable (features do not exist)

Answer cache, document download, conversation sharing, conversation search. If any is added, it needs its own
revocation test before release.

## Known limitations

1. **Replaced documents hide old answers.** A new version of a document makes answers built on the old version
   disappear for everyone, even when the content barely changed. This fails closed on purpose; it may annoy users.
2. **Notice, not partial answer.** One closed source hides the whole answer, including parts built on documents
   the person can still open. Safe, but coarse.
3. **Export endpoint not directly tested** (see table).
4. **Audit log keeps the person's original question text** after access is lost. This is by design for audit; the
   audit endpoints are level 4 only.
5. **Uploader keeps delete rights** on their own document after losing access to it
   (see `docs/security/AUTHORIZATION_COVERAGE.md`, gap 3). Undecided.
6. **Matrix uses one demo company and one throwaway user**, with a local model. It proves the behaviour exists,
   not that every configuration is covered.
