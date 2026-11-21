"""The model provider is a setting: local Ollama by default, or a hosted model (Anthropic, Groq, OpenAI-compatible)."""
import asyncio

import pytest

pytest.importorskip("httpx")

from app import config  # noqa: E402
from app.services import llm  # noqa: E402


class Resp:
    status_code = 200

    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


@pytest.fixture
def sent(monkeypatch):
    seen = {}

    async def fake_post(url, payload, headers, timeout):
        seen.update(url=url, payload=payload, headers=headers or {})
        return Resp(seen["reply"])

    monkeypatch.setattr(llm, "_post", fake_post)
    monkeypatch.setattr(config, "LLM_MODEL", "main-model")
    for name in ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "LLM_API_KEY"):
        monkeypatch.setattr(config, name, "")
    return seen


def chat(**kw):
    return asyncio.run(llm.chat("sys", "hello", **kw))


def test_anthropic_request_and_reply(monkeypatch, sent):
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k-test")
    sent["reply"] = {"content": [{"type": "text", "text": " answer "}]}
    assert chat(num_predict=50) == "answer"
    assert sent["url"] == llm.ANTHROPIC_URL
    assert sent["headers"]["x-api-key"] == "k-test"
    assert sent["payload"]["model"] == "main-model" and sent["payload"]["max_tokens"] == 50
    assert sent["payload"]["system"] == "sys"
    assert sent["payload"]["messages"] == [{"role": "user", "content": "hello"}]


def test_groq_request_and_reply(monkeypatch, sent):
    monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(config, "GROQ_API_KEY", "g-test")
    sent["reply"] = {"choices": [{"message": {"content": "hi there"}}]}
    assert chat(model="llama-3.1-8b-instant") == "hi there"
    assert sent["url"] == llm.GROQ_URL
    assert sent["headers"]["authorization"] == "Bearer g-test"
    assert sent["payload"]["model"] == "llama-3.1-8b-instant"
    assert sent["payload"]["messages"][0] == {"role": "system", "content": "sys"}


def test_openai_compatible_uses_the_base_url(monkeypatch, sent):
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(config, "LLM_API_KEY", "o-test")
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://example.test/v1/")
    sent["reply"] = {"choices": [{"message": {"content": "ok"}}]}
    assert chat() == "ok"
    assert sent["url"] == "https://example.test/v1/chat/completions"


def test_structured_replies_get_the_schema_in_the_prompt_and_fences_removed(monkeypatch, sent):
    monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(config, "GROQ_API_KEY", "g")
    sent["reply"] = {"choices": [{"message": {"content": '```json\n{"a": 1}\n```'}}]}
    assert chat(schema={"type": "object"}) == '{"a": 1}'
    assert "JSON schema" in sent["payload"]["messages"][0]["content"]
    assert sent["payload"]["response_format"] == {"type": "json_object"}


def test_a_local_model_tag_is_never_sent_to_a_hosted_provider(monkeypatch, sent):
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    sent["reply"] = {"content": [{"type": "text", "text": "x"}]}
    chat(model="qwen2.5:3b")
    assert sent["payload"]["model"] == "main-model"


def test_missing_key_or_model_fails_cleanly_without_a_request(monkeypatch, sent):
    monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
    with pytest.raises(llm.LLMUnavailable):
        chat()
    monkeypatch.setattr(config, "GROQ_API_KEY", "g")
    monkeypatch.setattr(config, "LLM_MODEL", "qwen2.5:7b")  # still the local default
    with pytest.raises(llm.LLMUnavailable):
        chat()
    assert "url" not in sent


def test_unknown_provider_is_refused(monkeypatch, sent):
    monkeypatch.setattr(config, "LLM_PROVIDER", "nope")
    with pytest.raises(llm.LLMUnavailable):
        chat()


def test_ollama_is_still_the_default_path(monkeypatch, sent):
    monkeypatch.setattr(config, "LLM_PROVIDER", "ollama")
    sent["reply"] = {"message": {"content": " local "}}
    assert chat(model="qwen2.5:3b") == "local"
    assert sent["url"].endswith("/api/chat") and sent["payload"]["model"] == "qwen2.5:3b"
    assert sent["headers"] == {}


def test_the_api_key_never_appears_in_an_error(monkeypatch, sent):
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "SECRET-KEY-123")

    async def boom(*a, **k):
        raise llm.LLMUnavailable("Model server returned status 401")

    monkeypatch.setattr(llm, "_post", boom)
    with pytest.raises(llm.LLMUnavailable) as err:
        chat()
    assert "SECRET-KEY-123" not in str(err.value)
