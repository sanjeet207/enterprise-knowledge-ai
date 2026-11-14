from app import config


def test_depth_picks_its_model(monkeypatch):
    monkeypatch.setenv("ANSWERER_QUICK_MODEL", "small:1b")
    monkeypatch.delenv("ANSWERER_DEEP_MODEL", raising=False)
    monkeypatch.delenv("ANSWERER_MODEL", raising=False)
    assert config.answer_model("quick") == "small:1b"
    assert config.answer_model("deep") == config.LLM_MODEL
    assert config.answer_model("standard") == config.LLM_MODEL


def test_unset_means_the_normal_answerer_model(monkeypatch):
    for d in ("QUICK", "STANDARD", "DEEP"):
        monkeypatch.delenv(f"ANSWERER_{d}_MODEL", raising=False)
    monkeypatch.setenv("ANSWERER_MODEL", "main:7b")
    assert config.answer_model("quick") == "main:7b"
