import numpy as np

from app.services import embedder


def test_nomic_gets_task_prefixes():
    assert embedder.prefix_for("nomic-embed-text", "document") == "search_document: "
    assert embedder.prefix_for("nomic-embed-text:latest", "query") == "search_query: "


def test_other_models_get_none():
    assert embedder.prefix_for("bge-m3", "query") == ""
    assert embedder.prefix_for("sentence-transformers/all-MiniLM-L6-v2", "document") == ""


def test_normalize_gives_unit_rows_and_survives_zero():
    out = embedder.normalize([[3.0, 4.0], [0.0, 0.0]])
    assert np.allclose(np.linalg.norm(out[0]), 1.0) and np.allclose(out[1], 0.0)
