from app.services.answer_check import accept_refinement, parse_refined_question

Q = "leave carry forward how many"


def test_a_clearer_question_is_accepted():
    assert accept_refinement(Q, "How many days of leave can be carried forward?") == "How many days of leave can be carried forward?"


def test_an_added_number_is_refused():
    assert accept_refinement(Q, "How many of the 24 leave days can be carried forward?") == Q


def test_a_dropped_number_is_refused():
    q = "Can I work remotely 3 days a week"
    assert accept_refinement(q, "Can employees work remotely?") == q


def test_a_dropped_part_is_refused():
    q = "How many days of leave do I get and how many can be carried forward"
    assert accept_refinement(q, "How many days of leave do employees get?") == q


def test_an_answer_is_refused():
    assert accept_refinement(Q, "Answer: leave can be carried forward") == Q
    assert accept_refinement(Q, "Yes, leave carry forward is allowed [1]") == Q


def test_a_runaway_rewrite_is_refused():
    assert accept_refinement("leave carry forward", " ".join(["leave carry forward"] * 40)) == "leave carry forward"


def test_multi_line_or_empty_is_refused():
    assert accept_refinement(Q, "How many days?\nAlso tell me more.") == Q
    assert accept_refinement(Q, "") == Q


def test_unchanged_is_fine():
    q = "How many days of annual leave do employees get?"
    assert accept_refinement(q, q) == q


def test_parse_handles_bad_json():
    assert parse_refined_question("not json", Q) == Q
    assert parse_refined_question('{"refined_question": 5}', Q) == Q
    assert parse_refined_question('{"refined_question": "How many leave days can be carried forward?"}', Q).startswith("How many")
