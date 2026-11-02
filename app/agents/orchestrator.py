"""Orchestrator: runs the agents in order, enforces retry limits, and writes the audit record.

Plain code, not a model. Access control is decided by the retriever's SQL filter, never by an agent.
"""
import time

from app import config
from app.agents import answerer, corrector, planner, rewriter, validator
from app.agents.base import Trace
from app.services import audit
from app.services.answer_check import cited_numbers, is_insufficient, strip_invalid_citations, uncited_sentences
from app.services.llm import LLMUnavailable

# One message for "nothing found" and "not relevant": a refusal must not reveal whether
# a restricted document exists.
REFUSAL = ("I can only answer from company documents you are authorized to access, "
           "and I couldn't find a reliable answer to this question.")
NO_ANSWER = "The documents available to you don't contain enough information to answer this."
UNVERIFIED = "I couldn't produce an answer that is backed by your documents, so I'm not showing one."


def _now() -> float:
    return time.perf_counter()


async def answer_question(user, query: str, top_k: int, retriever) -> dict:
    started = _now()
    trace = Trace()
    notes: list[str] = []
    question = query

    def finish(outcome, answer, sources=None, top_score=None, model=None):
        sources = sources or []
        audit.log_event(user, query, outcome, top_score, sources, answer, model,
                        int((_now() - started) * 1000), " | ".join(notes) or None, trace.steps)
        corrected = question if question.lower() != query.lower() else None
        return {"query": query, "corrected_query": corrected, "outcome": outcome,
                "answer": answer, "sources": sources}

    searches: list[list[dict]] = []  # every result list, in order

    def search(text: str) -> tuple[list[dict], float]:
        t = _now()
        hits = retriever.run(user, text, top_k)
        score = hits[0]["rerank_score"] if hits else 0.0
        titles = ", ".join(str(h["metadata"].get("title")) for h in hits)
        trace.add("retriever", t, f"score {score:.3f}: {titles}" if titles else f"score {score:.3f}")
        searches.append(hits)
        return hits, score

    def observe(text: str, hits: list[dict], score: float) -> dict:
        """What the planner is told about a search: titles and short snippets of allowed results only."""
        strong = score >= config.REFUSAL_THRESHOLD
        return {"query": text, "verdict": "strong match" if strong else "weak match",
                "results": [(h["metadata"].get("title") or "untitled",
                             " ".join(h["parent_content"].split())[:110]) for h in hits[:3]]}

    # 1. Corrector: fix typos. Cosmetic, so a model failure must not block the question.
    t = _now()
    try:
        question = await corrector.run(query)
    except LLMUnavailable:
        question = query
    changed = question.lower() != query.lower()
    trace.add("corrector", t, f"-> {question}" if changed else "no change")
    if changed:
        notes.append(f"corrected: {question}")

    # 2. Retriever (access filtered in SQL).
    reranked, top_score = search(question)
    tried = {question.lower()}
    extra_searches = 0

    # 3. Planner: a bounded loop that either finishes or asks for one more search. It can only call
    #    the same access-filtered retriever, at most PLANNER_MAX_SEARCHES searches in total.
    if config.PLANNER_ENABLED:
        observations = [observe(question, reranked, top_score)]
        while len(searches) < config.PLANNER_MAX_SEARCHES:
            t = _now()
            try:
                action, next_query = await planner.run(question, observations,
                                                       config.PLANNER_MAX_SEARCHES - len(searches))
            except LLMUnavailable:
                action, next_query = "finish", ""
            if action != "search" or next_query.lower() in tried:
                trace.add("planner", t, "finish")
                break
            trace.add("planner", t, f"search: {next_query}")
            tried.add(next_query.lower())
            notes.append(next_query)
            extra_searches += 1
            alt, alt_score = search(next_query)
            observations.append(observe(next_query, alt, alt_score))
            if alt_score > top_score:
                top_score = alt_score
                reranked = alt
    # Safety net: still weak after the planner (or planner off), so try the plain rewriter once.
    if top_score < config.REFUSAL_THRESHOLD:
        t = _now()
        try:
            variants = await rewriter.run(question)
        except LLMUnavailable:
            variants = []
        variants = [v for v in variants if v.lower() not in tried]
        trace.add("rewriter", t, f"{len(variants)} queries")
        notes.extend(variants)  # recorded even when they do not help
        for variant in variants:
            alt, alt_score = search(variant)
            if alt_score > top_score:
                reranked, top_score = alt, alt_score

    # When several searches ran, combine them: keep relevant passages only, best first, no duplicates.
    if len(searches) > 1 and top_score >= config.REFUSAL_THRESHOLD:
        pool: dict[str, dict] = {}
        for hits in searches:
            for h in hits:
                if h["rerank_score"] >= config.REFUSAL_THRESHOLD:
                    key = h["parent_content"]
                    if key not in pool or h["rerank_score"] > pool[key]["rerank_score"]:
                        pool[key] = h
        reranked = sorted(pool.values(), key=lambda h: h["rerank_score"], reverse=True)[:min(5, top_k + 1)]

    # 4. Still not relevant: refuse without calling the answering agents.
    if not reranked or top_score < config.REFUSAL_THRESHOLD:
        return finish("refused", REFUSAL, top_score=top_score)

    passages = [p["parent_content"] for p in reranked]
    model = config.agent_model(answerer.NAME)

    try:
        # 5. Answerer, with one retry if it forgot to cite.
        t = _now()
        answer = await answerer.run(question, passages)
        trace.add("answerer", t, "insufficient" if is_insufficient(answer) else f"drafted: {answer}")
        if not is_insufficient(answer) and not cited_numbers(answer, len(passages)):
            t = _now()
            answer = await answerer.run(question, passages, strict=True)
            trace.add("answerer", t, "retry: citations")

        # 6. Validator: every claim must be supported; regenerate a bounded number of times.
        if config.VALIDATOR_ENABLED:
            for attempt in range(config.VALIDATOR_MAX_RETRIES + 1):
                if is_insufficient(answer) or not cited_numbers(answer, len(passages)):
                    break
                # Plain-code rule first: every factual sentence must carry a citation.
                missing = uncited_sentences(answer, len(passages))
                if missing:
                    trace.add("validator", _now(), f"uncited: {missing[0][:150]}")
                    if attempt == config.VALIDATOR_MAX_RETRIES:
                        return finish("unverified", UNVERIFIED, top_score=top_score, model=model)
                    t = _now()
                    answer = await answerer.run(question, passages, strict=True,
                                                 feedback=f"this sentence has no source number: {missing[0]}")
                    trace.add("answerer", t, f"retry: citations: {answer}")
                    continue
                t = _now()
                ok, raw = await validator.run(question, answer, passages)
                trace.add("validator", t, "SUPPORTED" if ok else f"UNSUPPORTED {raw[:300]}")
                if ok:
                    break
                if attempt == config.VALIDATOR_MAX_RETRIES:
                    return finish("unverified", UNVERIFIED, top_score=top_score, model=model)
                t = _now()
                answer = await answerer.run(question, passages, strict=True, grounding=True, feedback=raw)
                trace.add("answerer", t, f"retry: grounding: {answer}")
    except LLMUnavailable:
        finish("error", None, top_score=top_score, model=model)
        raise

    if is_insufficient(answer):
        return finish("no_answer", NO_ANSWER, top_score=top_score, model=model)

    cited = cited_numbers(answer, len(passages))
    if not cited:
        return finish("unverified", UNVERIFIED, top_score=top_score, model=model)

    answer = strip_invalid_citations(answer, len(passages))
    sources = [
        {"number": n, "title": reranked[n - 1]["metadata"].get("title"),
         "score": round(reranked[n - 1]["rerank_score"], 4)}
        for n in cited
    ]
    return finish("answered", answer, sources, top_score, model)
