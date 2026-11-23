from scripts import hardcorp_data as h

LEVEL = {"analyst": 1, "manager": 2, "director": 3}
DOCS = {d["title"]: d for d in h.build_documents()}
CASES = h.all_cases()


def _level(case):
    return LEVEL[case["user"].split("@")[0]]


def test_titles_are_unique_and_the_corpus_is_long_enough_to_be_hard():
    assert len(DOCS) == len(h.build_documents()) >= 30
    assert sum(len(d["text"].split()) for d in DOCS.values()) > 7000
    assert all(len(d["text"].split()) > 150 for d in DOCS.values())  # several 200-word chunks per document, not one paragraph


def test_every_expected_phrase_appears_in_the_document_the_question_names():
    for c in CASES:
        if c["category"] == "answerable":
            text = DOCS[c["expect_doc"]]["text"].lower()
            assert any(p.lower() in text for p in c["must_contain_any"]), c["question"]
        if c["category"] == "multi_part":
            text = " ".join(DOCS[t]["text"].lower() for t in c["expect_docs"])
            for group in c["must_contain_groups"]:
                assert any(p.lower() in text for p in group), (c["question"], group)


def test_every_answerable_question_is_asked_by_someone_allowed_to_read_its_documents():
    for c in CASES:
        if c["category"] in ("answerable", "multi_part"):
            assert all(DOCS[t]["level"] <= _level(c) for t in c["expect_docs"]), c["question"]


def test_restricted_questions_name_facts_that_exist_only_above_the_askers_level():
    for c in CASES:
        if c["category"] == "restricted":
            visible = " ".join(d["text"].lower() for d in DOCS.values() if d["level"] <= _level(c))
            hidden = " ".join(d["text"].lower() for d in DOCS.values() if d["level"] > _level(c))
            for phrase in c["forbidden"]:
                assert phrase.lower() in hidden and phrase.lower() not in visible, (c["question"], phrase)


def test_the_corpus_has_the_hard_cases_it_claims():
    kinds = {c["kind"] for c in CASES}
    assert {"region", "current-version", "old-version", "exact-term", "multi-document", "ambiguous", "conflict",
            "restricted", "not-in-documents"} <= kinds
    assert "superseded" in DOCS["Travel and Expense Policy 2023"]["text"]
    assert "no longer maintained" in DOCS["Employee FAQ 2022"]["text"]


def test_the_generator_is_deterministic():
    assert h.build_documents() == h.build_documents()
