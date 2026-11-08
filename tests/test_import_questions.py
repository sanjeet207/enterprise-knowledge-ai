from scripts.import_questions import build_cases

TITLES = {"Employee Leave Policy", "Executive Compensation Framework"}


def row(**kw):
    base = {"asking_as": "analyst", "type": "answerable", "question": "How many days of leave do I get?",
            "document_title": "Employee Leave Policy", "key_phrases": "24 | twenty-four", "secret_phrases": ""}
    base.update(kw)
    return base


def test_answerable_row_becomes_a_case():
    cases, problems = build_cases([row()], TITLES)
    assert not problems
    assert cases == [{"category": "answerable", "user": "analyst@acme.test", "question": "How many days of leave do I get?",
                      "expect_doc": "Employee Leave Policy", "must_contain_any": ["24", "twenty-four"]}]


def test_blocked_row_lists_what_must_not_appear():
    cases, problems = build_cases([row(type="blocked", document_title="", key_phrases="", secret_phrases="2.5 crore|bonus pool")], TITLES)
    assert not problems and cases[0]["category"] == "restricted" and cases[0]["forbidden"] == ["2.5 crore", "bonus pool"]


def test_problems_name_the_row_and_nothing_is_guessed():
    rows = [row(asking_as="ceo"), row(type="maybe"), row(question="hi"), row(document_title="leave policy"),
            row(key_phrases=""), row(type="blocked", secret_phrases="")]
    cases, problems = build_cases(rows, TITLES)
    assert len(problems) == 6 and problems[0].startswith("row 2") and problems[-1].startswith("row 7")


def test_blank_rows_are_skipped_and_other_types_map():
    rows = [{"asking_as": "", "type": "", "question": ""}, row(type="not_in_documents", document_title="", key_phrases=""),
            row(type="off_topic", document_title="", key_phrases=""),
            row(type="general", document_title="", key_phrases="paris")]
    cases, problems = build_cases(rows, TITLES)
    assert not problems and [c["category"] for c in cases] == ["unsupported", "off_topic", "general"]
