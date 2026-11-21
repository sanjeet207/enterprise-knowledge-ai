"""The startup warm-up must never stop the server from starting."""
from app import main


def test_warm_up_swallows_model_errors(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("no model")

    monkeypatch.setattr("app.services.embedder.embed_texts", boom)
    main._warm_up_models()  # must not raise


def test_warm_up_calls_embedder_and_reranker(monkeypatch):
    calls = []
    monkeypatch.setattr("app.services.embedder.embed_texts", lambda *a, **k: calls.append("embed"))
    monkeypatch.setattr("app.services.reranker.rerank_passages", lambda *a, **k: calls.append("rerank"))
    main._warm_up_models()
    assert calls == ["embed", "rerank"]
