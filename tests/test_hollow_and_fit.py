from app.services.answer_check import is_hollow, parse_fit


def test_only_citation_markers_is_hollow():
    assert is_hollow("[1]")
    assert is_hollow("[1] [2].")
    assert is_hollow("")


def test_real_sentences_are_not_hollow():
    assert not is_hollow("Yes [1].")
    assert not is_hollow("Claims are due within 30 days [1].")
    assert not is_hollow("[1] Travel claims must be submitted within 30 days of travel.")


def test_parse_fit():
    assert parse_fit('{"answers_question": false}') is False
    assert parse_fit('{"answers_question": true}') is True
    assert parse_fit("not json") is True  # fails open: the claim validator still runs
    assert parse_fit('{"answers_question": "no"}') is True
