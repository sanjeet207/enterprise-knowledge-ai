from app.services.answer_check import titled_passage


def test_title_goes_on_a_first_line():
    assert titled_passage("The hotel limit is INR 9,000.", "Travel and Expense Policy 2023") == \
        "Document: Travel and Expense Policy 2023\nThe hotel limit is INR 9,000."


def test_no_title_leaves_the_passage_unchanged():
    assert titled_passage("Text.", None) == "Text."
    assert titled_passage("Text.", "   ") == "Text."


def test_title_is_flattened_and_limited():
    out = titled_passage("Body.", "A\nB " + "x" * 400)
    assert out.split("\n")[0].startswith("Document: A B x")
    assert len(out.split("\n")[0]) <= len("Document: ") + 150
