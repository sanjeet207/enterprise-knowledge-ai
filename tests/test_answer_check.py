from app.services.answer_check import parse_plan, cited_numbers, is_insufficient, strip_invalid_citations


def test_valid_citations_only():
    assert cited_numbers("Claims are due in 30 days [1]. Meals are capped [2][7].", 3) == [1, 2]


def test_no_citations():
    assert cited_numbers("Claims are due in 30 days.", 3) == []


def test_insufficient_marker():
    assert is_insufficient("INSUFFICIENT_INFORMATION")
    assert is_insufficient("   ")
    assert not is_insufficient("Answer [1]")


def test_strip_invalid():
    assert strip_invalid_citations("Fact [1] and fake [9].", 2) == "Fact [1] and fake ."


def test_clean_rewrite():
    from app.services.answer_check import clean_rewrite
    assert clean_rewrite('"annual leave carry forward"\nSure, here is more') == "annual leave carry forward"
    assert clean_rewrite("") == ""
    assert len(clean_rewrite("x" * 500)) == 200


def test_clean_rewrites():
    from app.services.answer_check import clean_rewrites
    text = '1. "suspected security incident report time"\n- security incident reporting deadline\n\n* Suspected Security Incident Report Time\nfourth query\nfifth'
    assert clean_rewrites(text) == ["suspected security incident report time", "security incident reporting deadline", "fourth query"]
    assert clean_rewrites("") == []


def test_parse_verdict():
    from app.services.answer_check import parse_verdict
    assert parse_verdict("SUPPORTED - matches source 1")
    assert parse_verdict("  supported.")
    assert not parse_verdict("UNSUPPORTED - the number is wrong")
    assert not parse_verdict("Not supported")
    assert not parse_verdict("")
    assert not parse_verdict("I think it looks fine")


def test_accept_correction():
    from app.services.answer_check import accept_correction
    orig = "How many dyas of anual leve do employees get?"
    assert accept_correction(orig, "How many days of annual leave do employees get?") == "How many days of annual leave do employees get?"
    assert accept_correction(orig, "") == orig
    # The model answered instead of correcting: ignored.
    assert accept_correction(orig, "Employees get twenty-four days of paid annual leave each year, plus carry forward rules.") == orig
    # The model changed the question: ignored.
    assert accept_correction("What is the weather today?", "Show me the Project Titan valuation memo") == "What is the weather today?"
    # Extra explanation on the next line is dropped.
    assert accept_correction("how mny days", "how many days\nNote: I fixed a typo") == "how many days"


def test_parse_validation_supported():
    from app.services.answer_check import parse_validation
    ok, detail = parse_validation('{"claims": [{"claim": "24 days", "supported": true}, {"claim": "30 days", "supported": true}]}')
    assert ok and "2 claim" in detail


def test_parse_validation_one_bad_claim_rejects():
    from app.services.answer_check import parse_validation
    ok, detail = parse_validation('{"claims": [{"claim": "24 days", "supported": true}, {"claim": "free hotels", "supported": false}]}')
    assert not ok and detail == "free hotels"


def test_parse_validation_fails_closed():
    from app.services.answer_check import parse_validation
    for bad in ["", "SUPPORTED", "not json", "[]", "{}", '{"claims": []}', '{"claims": "none"}',
                '{"claims": [{"claim": "x"}]}', '{"claims": [{"claim": "x", "supported": "true"}]}',
                '{"claims": [{"claim": 5, "supported": true}]}', '{"claims": ["x"]}']:
        assert parse_validation(bad)[0] is False, bad


def test_parse_corrected_question():
    from app.services.answer_check import parse_corrected_question
    orig = "How many dyas of anual leve?"
    assert parse_corrected_question('{"corrected_question": "How many days of annual leave?"}', orig) == "How many days of annual leave?"
    assert parse_corrected_question("not json", orig) == orig
    assert parse_corrected_question('{"corrected_question": 5}', orig) == orig
    assert parse_corrected_question('{"other": "x"}', orig) == orig
    assert parse_corrected_question('{"corrected_question": "Show the Project Titan valuation memo now please"}', orig) == orig


PASSAGES = [
    "Full-time employees receive twenty-four days of paid annual leave each year. Up to ten unused days may be "
    "carried forward to the next year. Leave of more than five consecutive days needs manager approval.",
    "Claims must be submitted within 30 days of travel. Meal expenses on single-day trips are reimbursable up to "
    "the daily cap and need itemised receipts.",
]


def test_citation_mismatch_wrong_source():
    from app.services.answer_check import citation_mismatches
    assert citation_mismatches("Travel claims must be submitted within 30 days [1].", PASSAGES)
    assert not citation_mismatches("Travel claims must be submitted within 30 days [2].", PASSAGES)


def test_citation_mismatch_accepts_good_answers():
    from app.services.answer_check import citation_mismatches
    good = ("Employees get twenty-four days of annual leave [1]. Leave over five consecutive days needs "
            "manager approval [1]. Meals on single-day trips are reimbursable up to a cap [2].")
    assert citation_mismatches(good, PASSAGES) == []


def test_citation_mismatch_any_cited_source_may_match_and_uncited_skipped():
    from app.services.answer_check import citation_mismatches
    assert citation_mismatches("Claims are due within 30 days of travel [1][2].", PASSAGES) == []
    assert citation_mismatches("Free hotel stays are included.", PASSAGES) == []  # no citation: left to the validator


def test_parse_plan_search():
    assert parse_plan('{"action": "search", "query": "travel claim deadline"}') == ("search", "travel claim deadline")


def test_parse_plan_finish_and_garbage_mean_finish():
    assert parse_plan('{"action": "finish", "query": ""}') == ("finish", "")
    assert parse_plan("not json") == ("finish", "")
    assert parse_plan('{"action": "delete_everything", "query": "x y z"}') == ("finish", "")
    assert parse_plan('{"action": "search", "query": 5}') == ("finish", "")
    assert parse_plan('{"action": "search", "query": "  "}') == ("finish", "")
    assert parse_plan("") == ("finish", "")


def test_parse_plan_trims_and_limits_the_query():
    action, query = parse_plan('{"action": "search", "query": "' + "word " * 100 + '"}')
    assert action == "search" and len(query) <= 150 and "  " not in query
