import copy

from app.services import conversations
from app.services.conversations import REDACTED_NOTICE, apply_current_access, with_current_access
from app.services.users import User

TITAN = "Project Titan Acquisition Valuation Memo"
OPEN_ID, CLOSED_ID = "doc-open", "doc-closed"


def answer(text, *sources):
    return {"id": 2, "role": "assistant", "content": text, "outcome": "answered", "sources": list(sources), "rating": None}


def source(doc_id=None, title="Leave Policy"):
    return {"number": 1, "title": title, "document_id": doc_id, "score": 0.9}


def show(messages, ids=(OPEN_ID,), titles=("leave policy",)):
    return apply_current_access(messages, set(ids), set(titles))


def test_answer_on_a_document_still_open_is_unchanged():
    messages = [answer("20 days [1]", source(OPEN_ID))]
    assert show(messages) == messages


def test_answer_on_a_document_no_longer_open_is_replaced_and_names_nothing():
    out = show([answer("The deal is valued at 40 crore [1]", source(CLOSED_ID, TITAN))])[0]
    assert out["content"] == REDACTED_NOTICE and out["outcome"] == "redacted" and out["redacted"] is True
    assert out["sources"] == []
    assert TITAN not in str(out) and "40 crore" not in str(out)


def test_one_closed_source_among_open_ones_hides_the_whole_answer():
    out = show([answer("text", source(OPEN_ID), source(CLOSED_ID, TITAN))])[0]
    assert out["outcome"] == "redacted" and out["sources"] == []


def test_the_persons_own_questions_and_refusals_stay():
    question = {"id": 1, "role": "user", "content": "What is the Titan valuation?", "outcome": None, "sources": None, "rating": None}
    refusal = {"id": 3, "role": "assistant", "content": "I can't help with that.", "outcome": "refused", "sources": [], "rating": None}
    assert show([question, refusal]) == [question, refusal]


def test_older_messages_without_a_document_id_are_matched_by_title_ignoring_case():
    assert show([answer("x", source(None, "LEAVE policy"))])[0]["outcome"] == "answered"


def test_older_message_whose_title_is_not_open_is_hidden():
    assert show([answer("x", source(None, TITAN))])[0]["outcome"] == "redacted"


def test_a_source_with_no_title_and_no_id_fails_closed():
    assert show([answer("x", source(None, None))])[0]["outcome"] == "redacted"


def test_the_document_id_wins_over_a_matching_title():
    # a different document may reuse the title; only the id says whether this one is still open
    assert show([answer("x", source(CLOSED_ID, "Leave Policy"))])[0]["outcome"] == "redacted"


def test_the_stored_messages_are_not_modified():
    messages = [answer("secret [1]", source(CLOSED_ID, TITAN))]
    before = copy.deepcopy(messages)
    show(messages)
    assert messages == before


def test_no_database_lookup_when_nothing_cites_a_source(monkeypatch):
    def boom(user):
        raise AssertionError("should not be called")
    monkeypatch.setattr(conversations, "accessible_documents", boom)
    user = User("u1", "acme", "a@acme.test", 1, True)
    plain = [{"id": 1, "role": "user", "content": "hi", "outcome": None, "sources": None, "rating": None}]
    assert with_current_access(user, plain) == plain


def test_loading_uses_the_persons_current_access(monkeypatch):
    user = User("u1", "acme", "a@acme.test", 2, True)
    monkeypatch.setattr(conversations, "accessible_documents", lambda u: ({OPEN_ID}, {"leave policy"}))
    out = with_current_access(user, [answer("a", source(OPEN_ID)), answer("b", source(CLOSED_ID, TITAN))])
    assert [m["outcome"] for m in out] == ["answered", "redacted"]


def test_one_lost_source_among_five_hides_the_answer():
    sources = [source(f"d{i}", f"Doc {i}") for i in range(5)]
    out = show([answer("text", *sources)], ids={f"d{i}" for i in range(4)}, titles=())
    assert out[0]["outcome"] == "redacted" and out[0]["sources"] == []


def test_all_sources_lost_hides_the_answer():
    out = show([answer("text", source("a"), source("b"))], ids=(), titles=())
    assert out[0]["outcome"] == "redacted"


def test_a_document_replaced_by_a_newer_version_hides_answers_built_on_the_old_one():
    # the old version is archived (not published), the new one has a different id and is open
    out = show([answer("20 days [1]", source("old-version-id"))], ids={"new-version-id"}, titles=())
    assert out[0]["outcome"] == "redacted"


def test_nothing_open_at_all_hides_every_sourced_answer_but_not_the_persons_own_words():
    # a deactivated account or one moved to another company has no open documents
    question = {"id": 1, "role": "user", "content": "hello", "outcome": None, "sources": None, "rating": None}
    out = show([question, answer("x", source(OPEN_ID))], ids=(), titles=())
    assert out[0] == question and out[1]["outcome"] == "redacted"
