from app.services import compare

OLD = ("Full-time employees receive twenty-four days of paid leave. Up to 10 unused days may be carried forward. "
       "Leave of more than 5 days needs manager approval. Claims are due in 30 days.")
NEW = ("Full-time employees receive thirty days of paid leave. Up to 10 unused days may be carried forward. "
       "Leave of more than 5 days needs manager approval. Remote work needs written approval.")


def test_sentences_are_split_and_trimmed():
    assert compare.split_sentences("One thing. Two things!  Three?") == ["One thing.", "Two things!", "Three?"]
    assert compare.split_sentences("") == []


def test_identical_documents_have_no_changes():
    result = compare.diff(OLD, OLD)
    assert result["changes"] == [] and result["unchanged"] == 4


def test_changed_sentence_is_paired_not_split_into_add_and_remove():
    result = compare.diff(OLD, NEW)
    kinds = [c["type"] for c in result["changes"]]
    assert "changed" in kinds
    changed = next(c for c in result["changes"] if c["type"] == "changed")
    assert "twenty-four" in changed["before"] and "thirty" in changed["after"]
    assert result["unchanged"] == 2


def test_new_and_dropped_sentences_are_reported():
    result = compare.diff("Alpha policy is long. Beta rule applies here.", "Alpha policy is long. Gamma duty is brand new.")
    types = sorted(c["type"] for c in result["changes"])
    assert types in (["added", "removed"], ["changed"])


def test_pure_addition_and_removal():
    assert [c["type"] for c in compare.diff("One fact here.", "One fact here. Two facts there.")["changes"]] == ["added"]
    assert [c["type"] for c in compare.diff("One fact here. Two facts there.", "One fact here.")["changes"]] == ["removed"]


def test_change_list_is_capped_but_total_is_reported():
    old = " ".join(f"Item number {i} is alpha{i}." for i in range(100))
    new = " ".join(f"Entry value {i} is omega{i * 7}." for i in range(100))
    result = compare.diff(old, new)
    assert len(result["changes"]) <= compare.MAX_CHANGES and result["total_changes"] >= len(result["changes"])


def test_numbers_are_extracted_without_trailing_punctuation():
    assert compare.numbers("Pay 1,200.50 by day 30.") == {"1,200.50", "30"}


def test_summary_may_only_use_numbers_from_the_changes():
    changes = [{"type": "changed", "before": "Claims are due in 30 days.", "after": "Claims are due in 45 days."}]
    assert compare.numbers_grounded("- The claim window grows from 30 to 45 days.", changes)
    assert not compare.numbers_grounded("- The claim window grows from 30 to 60 days.", changes)


def test_prompt_lists_every_change_as_data():
    text = compare.changes_prompt([{"type": "added", "before": "", "after": "New rule."}])
    assert text.startswith("<changes>") and "ADDED" in text and "New rule." in text
