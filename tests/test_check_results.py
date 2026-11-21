import json

from scripts import check_results as cr


def row(cat, passed=True, leaked=False):
    return {"category": cat, "passed": passed, "leaked": leaked}


def test_summarise_counts_by_category():
    s = cr.summarise([row("answerable"), row("answerable", passed=False), row("restricted")])
    assert s["categories"] == {"answerable": (1, 2), "restricted": (1, 1)}
    assert s["total"] == 3 and s["passed"] == 2 and s["leaks"] == 0


def test_check_passes_when_claim_matches():
    rows = [row("answerable"), row("answerable", passed=False)]
    assert cr.check("f", rows, {"total": 2, "answerable": (1, 2)}) == []


def test_check_flags_a_changed_number():
    rows = [row("answerable"), row("answerable")]
    problems = cr.check("f", rows, {"total": 2, "answerable": (1, 2)})
    assert any("answerable" in p for p in problems)


def test_check_flags_wrong_question_count():
    assert any("questions" in p for p in cr.check("f", [row("answerable")], {"total": 2, "answerable": (1, 1)}))


def test_any_leak_is_a_problem_even_if_claim_matches():
    rows = [row("restricted", leaked=True)]
    assert any("leak" in p for p in cr.check("f", rows, {"total": 1, "restricted": (1, 1)}))


def test_committed_results_match_published_claims():
    for name, claim in cr.CLAIMS.items():
        rows = json.loads((cr.EVAL_DIR / name).read_text())
        assert cr.check(name, rows, claim) == []
