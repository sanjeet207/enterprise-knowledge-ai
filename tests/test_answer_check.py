from app.services.answer_check import cited_numbers, is_insufficient, strip_invalid_citations


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
