"""Orchestrator tests with fake agents: no database, no model server."""
import asyncio

import pytest

from app import config
from app.agents import answerer, corrector, orchestrator, planner, rewriter, validator
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
    monkeypatch.setattr(config, "PLANNER_ENABLED", False)  # planner tests switch it on explicitly
    monkeypatch.setattr(config, "PLANNER_MAX_SEARCHES", 3)
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


# ---- planner -------------------------------------------------------------------------------------

class MultiRetriever:
    """Returns different passages per query so merging can be observed."""

    def __init__(self, by_query, default=None):
        self.by_query, self.default, self.calls = by_query, default or [], []

    def run(self, user, text, top_k):
        self.calls.append((user, text))
        return self.by_query.get(text, self.default)


def hit(text, score, title="Doc"):
    return {"parent_content": text, "metadata": {"title": title}, "rerank_score": score}


def planner_returns(mp, *decisions):
    queue = iter(decisions)
    seen = []

    async def fake(question, observations, remaining):
        seen.append((list(observations), remaining))
        return next(queue, ("finish", ""))

    mp.setattr(planner, "run", fake)
    mp.setattr(config, "PLANNER_ENABLED", True)
    return seen


def agents(events):
    return [s["agent"] for s in events[-1][0][-1]]


def test_planner_finish_means_single_search(env):
    events, calls, mp = env
    planner_returns(mp, ("finish", ""))
    retriever = FakeRetriever()
    out = run(retriever)
    assert out["outcome"] == "answered" and len(retriever.calls) == 1
    assert agents(events) == ["corrector", "retriever", "planner", "answerer", "validator"]


def test_planner_second_search_merges_both_results(env):
    events, calls, mp = env
    planner_returns(mp, ("search", "travel claim deadline"), ("finish", ""))
    retriever = MultiRetriever({
        "How many leave days?": [hit("Leave: 24 days.", 0.8, "Leave Policy")],
        "travel claim deadline": [hit("Travel claims within 30 days.", 0.6, "Travel Policy")],
    })
    seen_passages = []

    async def capture(q, passages, strict=False, grounding=False):
        seen_passages.extend(passages)
        return "Both apply [1][2]."

    mp.setattr(answerer, "run", capture)
    out = run(retriever)
    assert out["outcome"] == "answered"
    assert seen_passages == ["Leave: 24 days.", "Travel claims within 30 days."]  # best first, no duplicates
    assert [s["title"] for s in out["sources"]] == ["Leave Policy", "Travel Policy"]


def test_planner_is_bounded(env):
    events, calls, mp = env
    # a planner that always wants another, new search
    counter = iter(range(100))

    async def greedy(question, observations, remaining):
        return "search", f"query number {next(counter)}"

    mp.setattr(planner, "run", greedy)
    mp.setattr(config, "PLANNER_ENABLED", True)
    retriever = FakeRetriever()
    run(retriever)
    assert len(retriever.calls) == config.PLANNER_MAX_SEARCHES


def test_planner_repeating_a_query_stops_the_loop(env):
    events, calls, mp = env
    planner_returns(mp, ("search", "HOW MANY LEAVE DAYS?"))  # same as the first query
    retriever = FakeRetriever()
    run(retriever)
    assert len(retriever.calls) == 1


def test_planner_failure_falls_back_to_finish(env):
    events, calls, mp = env

    async def down(*a, **k):
        raise LLMUnavailable("down")

    mp.setattr(planner, "run", down)
    mp.setattr(config, "PLANNER_ENABLED", True)
    assert run(FakeRetriever())["outcome"] == "answered"


def test_planner_never_changes_who_is_searching(env):
    events, calls, mp = env
    planner_returns(mp, ("search", "another angle"), ("search", "third angle"))
    retriever = FakeRetriever()
    run(retriever)
    assert len(retriever.calls) == 3
    assert all(c[0].level == 1 and c[0].tenant_id == "acme" and c[0].id == "u1" for c in retriever.calls)


def test_planner_sees_only_returned_results_and_search_budget(env):
    events, calls, mp = env
    seen = planner_returns(mp, ("finish", ""))
    run(MultiRetriever({"How many leave days?": [hit("Leave: 24 days.", 0.8, "Leave Policy")]}))
    observations, remaining = seen[0]
    assert observations[0]["verdict"] == "strong match"
    assert observations[0]["results"] == [("Leave Policy", "Leave: 24 days.")]
    assert remaining == config.PLANNER_MAX_SEARCHES - 1


def test_planner_reformulation_rescues_weak_first_search(env):
    events, calls, mp = env
    planner_returns(mp, ("search", "suspected security incident"), ("finish", ""))
    retriever = MultiRetriever({
        "my laptop got hacked": [hit("irrelevant", 0.001, "Other")],
        "suspected security incident": [hit("Report within one hour.", 0.7, "Security Policy")],
    })
    out = run(retriever, "my laptop got hacked")
    assert out["outcome"] == "answered" and out["sources"][0]["title"] == "Security Policy"
    assert calls["rewriter"] == 0  # the planner already added a search


def test_weak_everywhere_still_refuses_identically(env):
    events, calls, mp = env
    planner_returns(mp, ("search", "weather forecast today"), ("finish", ""))
    out = run(MultiRetriever({}, default=[hit("nothing relevant", 0.0001)]), "What is the weather?")
    assert out["outcome"] == "refused" and out["answer"] == orchestrator.REFUSAL
    assert calls["answerer"] == 0


def test_weak_first_search_and_planner_finish_uses_rewriter_safety_net(env):
    events, calls, mp = env
    planner_returns(mp, ("finish", ""))
    out = run(FakeRetriever(score=0.0001))
    assert out["outcome"] == "refused" and calls["rewriter"] == 1


def test_rewriter_still_rescues_when_planner_search_is_also_weak(env):
    events, calls, mp = env
    planner_returns(mp, ("search", "some bad guess"), ("finish", ""))

    async def good_rewrite(q):
        calls["rewriter"] += 1
        return ["formal policy wording"]

    mp.setattr(rewriter, "run", good_rewrite)
    retriever = MultiRetriever({
        "what cheks are done": [hit("weak", 0.001, "Other")],
        "some bad guess": [hit("weak", 0.002, "Other")],
        "formal policy wording": [hit("Checks: KYC.", 0.5, "Onboarding Policy")],
    })
    out = run(retriever, "what cheks are done")
    assert out["outcome"] == "answered" and out["sources"][0]["title"] == "Onboarding Policy"
    assert calls["rewriter"] == 1
