import json

from app.services import research_core as rc


def test_parse_questions_cleans_dedupes_and_caps():
    raw = json.dumps({"questions": ["What is the leave policy?", "what is the leave policy?", "x", "  Travel   rules for staff  ",
                                    "Q3 about remote work", "Q4 about expenses", "Q5 about conduct", "Q6 about security"]})
    out = rc.parse_questions(raw, "request")
    assert out[0] == "What is the leave policy?"
    assert "Travel rules for staff" in out
    assert len(out) == rc.MAX_QUESTIONS
    assert "x" not in out


def test_parse_questions_falls_back_to_the_request():
    for raw in ("not json", "{}", '{"questions": "oops"}', '{"questions": []}', "[]"):
        assert rc.parse_questions(raw, "Summarise  the   leave rules") == ["Summarise the leave rules"]


def test_renumber_uses_one_number_per_title_across_sections():
    registry = {}
    a, used_a = rc.renumber("Leave is 20 days [1]. Carry over is 5 days [2].",
                            [{"number": 1, "title": "Leave Policy"}, {"number": 2, "title": "HR Handbook"}], registry)
    b, used_b = rc.renumber("Notice is 30 days [1].", [{"number": 1, "title": "HR Handbook"}], registry)
    assert a == "Leave is 20 days [1]. Carry over is 5 days [2]."
    assert b == "Notice is 30 days [2]."
    assert used_a == [1, 2] and used_b == [2]
    assert registry == {"Leave Policy": 1, "HR Handbook": 2}


def test_renumber_drops_markers_that_match_no_source():
    text, used = rc.renumber("Fact [1] and invented [9].", [{"number": 1, "title": "A"}], {})
    assert "[9]" not in text and used == [1]


def test_verify_summary_accepts_a_cited_summary():
    sections = ["Leave is 20 days [1]."]
    assert rc.verify_summary("Staff get leave [1].", sections, 1) is None


def test_verify_summary_rejects_uncited_and_empty():
    assert rc.verify_summary("  ", ["x [1]"], 1) == "empty"
    assert rc.verify_summary("Staff get leave. It is generous [1].", ["x [1]"], 1) is not None
    assert rc.verify_summary("Staff get leave.", ["x [1]"], 1) is not None


def test_verify_summary_rejects_nonexistent_source():
    assert rc.verify_summary("Staff get leave [3].", ["x [1]"], 1) is not None


def test_verify_summary_rejects_figures_not_in_findings():
    reason = rc.verify_summary("Staff get 25 days of leave [1].", ["Leave is 20 days [1]."], 1)
    assert reason and "25" in reason
    assert rc.verify_summary("Staff get 20 days of leave [1].", ["Leave is 20 days [1]."], 1) is None


def test_valid_conflicts_requires_both_statements_in_findings():
    sections = ["Notice is 30 days [1].", "Notice is 60 days [2]."]
    raw = json.dumps({"conflicts": [
        {"topic": "notice", "statement_a": "Notice is 30 days", "statement_b": "Notice is 60 days"},
        {"topic": "made up", "statement_a": "Notice is 30 days", "statement_b": "Notice is 90 days"},
        {"topic": "same", "statement_a": "Notice is 30 days", "statement_b": "Notice is 30 days [1]"},
    ]})
    out = rc.valid_conflicts(raw, sections)
    assert len(out) == 1 and out[0]["topic"] == "notice"


def test_valid_conflicts_tolerates_bad_input():
    for raw in ("nope", "{}", '{"conflicts": "x"}', '{"conflicts": [1, 2]}'):
        try:
            assert rc.valid_conflicts(raw, ["a"]) == []
        except AttributeError:
            raise AssertionError("must not raise on malformed items: " + raw)
