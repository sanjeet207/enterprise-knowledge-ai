import pytest

from scripts import keyword_experiment as k
from app.services.vector_store import VectorStoreService


def test_or_sql_swaps_both_uses_and_keeps_every_placeholder():
    base = VectorStoreService.SECURE_RRF_SQL
    out = k.or_sql(base)
    assert "plainto_tsquery" not in out and out.count("to_tsquery('english'") == 2
    assert out.count("%s") == base.count("%s")  # one parameter per use, as before


def test_or_sql_refuses_a_search_sql_it_does_not_recognise():
    with pytest.raises(AssertionError):
        k.or_sql("SELECT 1")


def test_the_two_queries_each_take_exactly_one_parameter():
    assert k.AND_QUERY.count("%s") == 1 and k.OR_QUERY.count("%s") == 1


def test_exact_term_set_is_well_formed_and_every_expected_document_exists_in_the_demo_data():
    import json
    from pathlib import Path
    cases = json.loads(Path("evaluation/exact_term_set.json").read_text())
    demo = Path("evaluation/demo_documents.md").read_text()
    assert len(cases) == 15
    for c in cases:
        assert c["category"] == "answerable" and c["question"].strip() and c["user"].endswith("@acme.test")
        assert f"## {c['expect_doc']}\n" in demo
