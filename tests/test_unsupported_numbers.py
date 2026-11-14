from app.services.answer_check import unsupported_numbers

P = ["Claims must be submitted within 30 days of the trip. The limit is 25,000 rupees."]


def test_figures_in_the_passages_pass():
    assert unsupported_numbers("Claims are due within 30 days [1].", P) == []
    assert unsupported_numbers("The limit is 25000 rupees [1].", P) == []


def test_a_wrong_figure_is_found():
    assert unsupported_numbers("Claims are due within 14 days [1].", P) == ["14"]


def test_citation_markers_are_ignored():
    assert unsupported_numbers("Submit within 30 days [1] [2].", P) == []


def test_no_figures_no_problem():
    assert unsupported_numbers("Yes, personal cloud storage is not allowed [1].", P) == []
