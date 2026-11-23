import copy

from app.services import conversations, reports
from app.services.reports import REDACTED_NOTICE, apply_current_access
from app.services.users import User

TITAN = "Project Titan Acquisition Valuation Memo"


def report(**over):
    base = {
        "request": "Summarise the deal and the leave rules", "summary": "Deal is 40 crore [1]; leave is 20 days [2].",
        "sections": [
            {"question": "Deal value?", "answer": "40 crore [1]", "sources": [1]},
            {"question": "Leave?", "answer": "20 days [2]", "sources": [2]},
        ],
        "inconsistencies": [{"topic": "x", "statement_a": "a", "statement_b": "b"}],
        "limitations": [],
        "sources": [{"number": 1, "title": TITAN, "document_id": "closed"}, {"number": 2, "title": "Leave Policy", "document_id": "open"}],
    }
    base.update(over)
    return base


def show(r, ids=("open",), titles=("leave policy",)):
    return apply_current_access(r, set(ids), set(titles))


def test_a_report_whose_sources_are_all_open_is_unchanged():
    r = report(sources=[{"number": 1, "title": "Leave Policy", "document_id": "open"}, {"number": 2, "title": "Leave Policy 2", "document_id": "open"}])
    assert show(r) is r


def test_the_finding_that_cites_a_closed_document_is_replaced_the_other_stays():
    out = show(report())
    assert out["sections"][0]["answer"] == REDACTED_NOTICE and out["sections"][0]["sources"] == []
    assert out["sections"][1]["answer"] == "20 days [2]"


def test_summary_and_inconsistencies_are_removed_because_they_mix_every_finding():
    out = show(report())
    assert out["summary"] is None and out["inconsistencies"] == [] and out["redacted"] is True


def test_the_closed_source_title_and_content_do_not_appear_anywhere_in_the_result():
    text = str(show(report()))
    assert TITAN not in text and "40 crore" not in text and "document_id': 'closed'" not in text


def test_only_open_sources_remain_and_the_person_is_told_why():
    out = show(report())
    assert [s["number"] for s in out["sources"]] == [2]
    assert any("no longer open" in note for note in out["limitations"])


def test_older_reports_with_titles_only_are_matched_by_title_and_fail_closed():
    old = report(sources=[{"number": 1, "title": TITAN}, {"number": 2, "title": "Leave Policy"}])
    out = show(old)
    assert out["sections"][0]["answer"] == REDACTED_NOTICE and out["sections"][1]["answer"] != REDACTED_NOTICE


def test_the_stored_report_is_not_modified():
    r = report()
    before = copy.deepcopy(r)
    show(r)
    assert r == before


def test_no_lookup_for_a_report_without_sources(monkeypatch):
    def boom(user):
        raise AssertionError("should not be called")
    monkeypatch.setattr(conversations, "accessible_documents", boom)
    plain = report(sources=[])
    assert reports.with_current_access(User("u", "acme", "a@acme.test", 1, True), plain) is plain


def test_loading_uses_the_persons_current_access(monkeypatch):
    monkeypatch.setattr(conversations, "accessible_documents", lambda u: ({"open"}, {"leave policy"}))
    out = reports.with_current_access(User("u", "acme", "a@acme.test", 2, True), report())
    assert out["redacted"] is True and out["sections"][0]["answer"] == REDACTED_NOTICE
