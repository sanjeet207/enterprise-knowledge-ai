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


def test_only_versioned_titles_are_shown():
    from app.services.answer_check import versioned_titles
    got = versioned_titles(["Travel and Expense Policy 2023", "Travel and Expense Policy 2025",
                            "Code of Conduct and Whistleblower Policy", None])
    assert got == {"Travel and Expense Policy 2023", "Travel and Expense Policy 2025"}


def test_version_marks_count_as_the_same_stem():
    from app.services.answer_check import versioned_titles
    assert versioned_titles(["Leave Policy v1", "Leave Policy v2.1"]) == {"Leave Policy v1", "Leave Policy v2.1"}


def test_distinct_documents_show_no_titles():
    from app.services.answer_check import versioned_titles
    assert versioned_titles(["Leave Policy India", "Leave Policy UK"]) == set()
    assert versioned_titles(["Same Title", "Same Title"]) == set()
