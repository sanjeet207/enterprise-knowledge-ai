"""One quick retry when the model server drops a request; no retry on a timeout."""
import asyncio

import pytest

httpx = pytest.importorskip("httpx")

from app.services import llm  # noqa: E402


class FakeResponse:
    def __init__(self, status, text="hello"):
        self.status_code = status
        self._text = text

    def json(self):
        return {"message": {"content": self._text}}


def fake_client(outcomes):
    calls = []

    class Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            calls.append(1)
            outcome = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    return Client, calls


def run(outcomes, monkeypatch):
    Client, calls = fake_client(outcomes)
    monkeypatch.setattr(llm.httpx, "AsyncClient", Client)
    monkeypatch.setattr(llm, "RETRY_PAUSE", 0)
    return asyncio.run(llm.chat("s", "u")), calls


def test_a_5xx_is_retried_once_and_then_works(monkeypatch):
    text, calls = run([FakeResponse(503), FakeResponse(200, "ok")], monkeypatch)
    assert text == "ok" and len(calls) == 2


def test_a_refused_connection_is_retried_once(monkeypatch):
    text, calls = run([httpx.ConnectError("no"), FakeResponse(200, "ok")], monkeypatch)
    assert text == "ok" and len(calls) == 2


def test_two_failures_give_up_cleanly(monkeypatch):
    with pytest.raises(llm.LLMUnavailable):
        run([FakeResponse(503), FakeResponse(503)], monkeypatch)


def test_a_timeout_is_not_retried(monkeypatch):
    Client, calls = fake_client([httpx.ReadTimeout("slow")])
    monkeypatch.setattr(llm.httpx, "AsyncClient", Client)
    with pytest.raises(llm.LLMUnavailable):
        asyncio.run(llm.chat("s", "u"))
    assert len(calls) == 1
