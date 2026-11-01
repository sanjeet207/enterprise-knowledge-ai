"""Orchestrator tests with fake agents: no database, no model server."""
import asyncio

import pytest

from app import config
from app.agents import answerer, corrector, orchestrator, rewriter, validator
from app.services.llm import LLMUnavailable


class User:
    id = "u1"
    tenant_id = "acme"
    level = 1
    email = "analyst@acme.test"


class FakeRetriever:
    def __init__(self, score=0.9):
        self.score = score
        self.calls = []

    def run(self, user, text, top_k):
        self.calls.append((user, text))
        if self.score is None:
            return []
        return [{"parent_content": "Employees receive twenty-four days of annual leave.",
                 "metadata": {"title": "Employee Leave Policy"}, "rerank_score": self.score}]


@pytest.fixture
def env(monkeypatch):
    events, calls = [], {"answerer": 0, "validator": 0, "rewriter": 0}

    async def fake_corrector(q):
        return q

    async def fake_answerer(q, passages, strict=False, grounding=False):
        calls["answerer"] += 1
        return "Employees receive twenty-four days [1]."

    async def fake_validator(q, a, passages):
        calls["validator"] += 1
        return True, "SUPPORTED"

    async def fake_rewriter(q):
        calls["rewriter"] += 1
        return []

    monkeypatch.setattr(corrector, "run", fake_corrector)
    monkeypatch.setattr(answerer, "run", fake_answerer)
    monkeypatch.setattr(validator, "run", fake_validator)
    monkeypatch.setattr(rewriter, "run", fake_rewriter)
    monkeypatch.setattr(orchestrator.audit, "log_event", lambda *a, **k: events.append((a, k)))
    monkeypatch.setattr(config, "VALIDATOR_ENABLED", True)
    monkeypatch.setattr(config, "VALIDATOR_MAX_RETRIES", 2)
    return events, calls, monkeypatch


def run(retriever, q="How many leave days?"):
    return asyncio.run(orchestrator.answer_question(User(), q, 3, retriever))


def test_answered_with_source(env):
    events, calls, _ = env
    out = run(FakeRetriever())
    assert out["outcome"] == "answered"
    assert out["sources"][0]["title"] == "Employee Leave Policy"
    assert [s["agent"] for s in events[0][0][-1]] == ["corrector", "retriever", "answerer", "validator"]


def test_weak_retrieval_refuses_without_answering(env):
    events, calls, _ = env
    out = run(FakeRetriever(score=0.0001))
    assert out["outcome"] == "refused" and out["answer"] == orchestrator.REFUSAL
    assert calls["answerer"] == 0 and calls["rewriter"] == 1


def test_nothing_found_refuses_identically(env):
    out_none = run(FakeRetriever(score=None))
    out_weak = run(FakeRetriever(score=0.0001))
    assert out_none["answer"] == out_weak["answer"]  # no signal that a restricted document exists


def test_validator_rejects_every_time_ends_unverified(env):
    events, calls, mp = env

    async def reject(q, a, p):
        calls["validator"] += 1
        return False, "UNSUPPORTED - number not in sources"

    mp.setattr(validator, "run", reject)
    out = run(FakeRetriever())
    assert out["outcome"] == "unverified" and out["answer"] == orchestrator.UNVERIFIED
    assert calls["answerer"] == 1 + config.VALIDATOR_MAX_RETRIES  # bounded regeneration
    assert calls["validator"] == 1 + config.VALIDATOR_MAX_RETRIES


def test_validator_rejects_once_then_passes(env):
    events, calls, mp = env
    verdicts = iter([(False, "UNSUPPORTED"), (True, "SUPPORTED")])

    async def flaky(q, a, p):
        return next(verdicts)

    mp.setattr(validator, "run", flaky)
    assert run(FakeRetriever())["outcome"] == "answered"
    assert calls["answerer"] == 2


def test_model_down_logs_error_and_raises(env):
    events, calls, mp = env

    async def down(*a, **k):
        raise LLMUnavailable("down")

    mp.setattr(answerer, "run", down)
    with pytest.raises(LLMUnavailable):
        run(FakeRetriever())
    assert events[-1][0][2] == "error"


def test_corrector_failure_does_not_block(env):
    events, calls, mp = env

    async def down(q):
        raise LLMUnavailable("down")

    mp.setattr(corrector, "run", down)
    assert run(FakeRetriever())["outcome"] == "answered"


def test_corrected_question_is_searched_and_reported(env):
    events, calls, mp = env

    async def fix(q):
        return "How many days of annual leave?"

    mp.setattr(corrector, "run", fix)
    retriever = FakeRetriever()
    out = run(retriever, "How mny dyas of anual leve?")
    assert retriever.calls[0][1] == "How many days of annual leave?"
    assert out["corrected_query"] == "How many days of annual leave?"
    assert out["query"] == "How mny dyas of anual leve?"  # the audit log keeps what the user typed


def test_retriever_always_receives_the_user(env):
    retriever = FakeRetriever()
    run(retriever)
    assert all(call[0].level == 1 and call[0].tenant_id == "acme" for call in retriever.calls)
