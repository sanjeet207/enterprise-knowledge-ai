"""Orchestrator: runs the agents in order, enforces retry limits, and writes the audit record.

Plain code, not a model. Access control is decided by the retriever's SQL filter, never by an agent.
"""
import time

from app import config
from app.agents import (answerer, corrector, fit_checker, general, general_checker, planner, refiner, rewriter, router,
                        validator)
from app.agents.base import Trace
from app.services import audit
from app.services.answer_check import (cited_numbers, is_hollow, is_insufficient, repair_neighbor_citation,
                                       strip_invalid_citations, titled_passage, uncited_sentences,
                                       unsupported_numbers)
from app.services import question_profile
from app.services.llm import LLMUnavailable

# One message for "nothing found" and "not relevant": a refusal must not reveal whether
# a restricted document exists.
REFUSAL = ("I can only answer from company documents you are authorized to access, "
           "and I couldn't find a reliable answer to this question.")
OFF_TOPIC = "That question isn't related to your company's documents, so I can't answer it here."
NO_ANSWER = "The documents available to you don't contain enough information to answer this."
UNVERIFIED = "I couldn't produce an answer that is backed by your documents, so I'm not showing one."
GENERAL_UNVERIFIED = "I couldn't produce a reliable general answer to this question, so I'm not showing one."


def _now() -> float:
    return time.perf_counter()


EXCERPT_CHARS = 500  # how much of a cited section is shown next to the answer

async def general_path(question: str, prof: dict, trace: Trace, finish, top_score: float):
    """Answer a non-company question from general knowledge, or return None so the caller refuses.

    Order matters: plain-code guard first (company words, override attempts), then the router, then a
    labelled answer that a checker must accept. Every "no" ends in the same refusal as before.
    """
    if not config.GENERAL_ENABLED:
        return None
    if question_profile.blocked_for_general(question):
        trace.add("router", _now(), "company-specific or override: not answered from general knowledge")
        return None
    t = _now()
    try:
        route = await router.run(question)
    except LLMUnavailable:
        route = "company"
    trace.add("router", t, f"route: {route}")
    if route != "general":
        return None
    model = general.model_for(prof["depth"])
    feedback = None
    try:
        for attempt in range(config.VALIDATOR_MAX_RETRIES + 1):
            t = _now()
            answer = await general.run(question, prof, feedback=feedback)
            if general.is_declined(answer):
                trace.add("general", t, "declined: needs company or live information")
                return None
            trace.add("general", t, f"{prof['depth']}/{prof['format']}: {answer}")
            t = _now()
            ok, reason = await general_checker.run(question, answer)
            trace.add("validator", t, "general answer accepted" if ok else f"rejected: {reason}")
            if ok:
                return finish("general", answer, [], top_score, model)
            feedback = reason
    except LLMUnavailable:
        finish("error", None, top_score=top_score, model=model)
        raise
    return finish("unverified", GENERAL_UNVERIFIED, top_score=top_score, model=model)


async def off_topic(question: str, trace: Trace) -> bool:
    """True when the question is plainly not about the company (weather, news, role-play...).

    Uses only the question, never documents, so the wording of a refusal cannot reveal whether a restricted document
    exists. Any doubt or model failure counts as "about the company": the normal refusal.
    """
    if not config.OFF_TOPIC_NOTICE:
        return False
    # Company words or an attempt to override the rules: never "not related", always the normal refusal.
    if question_profile.words(question) & question_profile.COMPANY_WORDS or question_profile.OVERRIDE_PATTERN.search(question):
        return False
    t = _now()
    try:
        route = await router.run(question)
    except LLMUnavailable:
        return False
    trace.add("router", t, f"relevance: {'not company' if route != 'company' else 'company'}")
    return route != "company"


async def answer_question(user, query: str, top_k: int, retriever, on_step=None) -> dict:
    started = _now()
    trace = Trace(listener=on_step)
    notes: list[str] = []
    question = query

    def finish(outcome, answer, sources=None, top_score=None, model=None):
        sources = sources or []
        audit.log_event(user, query, outcome, top_score, sources, answer, model,
                        int((_now() - started) * 1000), " | ".join(notes) or None, trace.steps)
        corrected = question if question.lower() != query.lower() else None
        # Step names and timings only. The detail text stays in the audit log (it can name documents).
        timings = [{"agent": step["agent"], "ms": step["ms"]} for step in trace.steps]
        return {"query": query, "corrected_query": corrected, "outcome": outcome,
                "answer": answer, "sources": sources, "trace": timings}

    searches: list[list[dict]] = []  # every result list, in order

    def search(text: str) -> tuple[list[dict], float]:
        t = _now()
        hits = retriever.run(user, text, top_k)
        score = max((h["rerank_score"] for h in hits), default=0.0)
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
    # Refiner (optional): when the first search matched only weakly, the model rewrites the question into its clearest
    #     form and that wording is used to SEARCH for better passages, before the system gives up on the question.
    #     The answerer and validator keep the person's own (typo-fixed) wording: measured earlier, answering the
    #     rewrite changed vocabulary and cost accuracy. A clear question with a strong match is never rewritten.
    first_score = top_score
    refined_ran = False
    if config.REFINER_ENABLED and (config.REFINER_ALWAYS or top_score < config.REFINER_BELOW):
        refined_ran = True
        t = _now()
        try:
            refined = await refiner.run(question)
        except LLMUnavailable:
            refined = question
        if refined.lower() != question.lower() and refined.lower() not in tried:
            tried.add(refined.lower())
            alt, alt_score = search(refined)
            trace.add("refiner", t, f"search with: {refined} (score {top_score:.3f} -> {max(top_score, alt_score):.3f})")
            notes.append(f"refined search: {refined}")
            if alt_score > top_score:
                reranked, top_score = alt, alt_score
        else:
            trace.add("refiner", t, "no change")
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

    def combine() -> list[dict]:
        """Combine several searches: keep relevant passages only, best first, no duplicates."""
        pool: dict[str, dict] = {}
        for hits in searches:
            for h in hits:
                if h["rerank_score"] >= config.REFUSAL_THRESHOLD:
                    key = h["parent_content"]
                    if key not in pool or h["rerank_score"] > pool[key]["rerank_score"]:
                        pool[key] = h
        return sorted(pool.values(), key=lambda h: h["rerank_score"], reverse=True)[:min(5, top_k + 1)]

    # A clear question that already matched strongly keeps its own best list: the always-on refiner may add a better
    # one, but never dilutes a strong match with extra passages.
    clear_match = refined_ran and first_score >= config.REFINER_BELOW and extra_searches == 0 and len(searches) == 2
    if len(searches) > 1 and top_score >= config.REFUSAL_THRESHOLD and not clear_match:
        reranked = combine()

    # 4. Still not relevant to any document this user may see. A question that is plainly not about the
    #    company may be answered from general knowledge, labelled as such; everything else is refused.
    prof = question_profile.profile(question)
    if not reranked or top_score < config.REFUSAL_THRESHOLD:
        general_result = await general_path(question, prof, trace, finish, top_score)
        if general_result is not None:
            return general_result
        if await off_topic(question, trace):
            return finish("refused", OFF_TOPIC, top_score=top_score)
        result = finish("refused", REFUSAL, top_score=top_score)
        result["can_request_access"] = True  # about the company, but nothing this person may see covers it
        return result
    trace.add("analysis", _now(), f"depth {prof['depth']}, format {prof['format']}")
    style = question_profile.style_for(prof["format"])
    style_kw = {"style": style} if style else {}

    # Model router: the question's depth picks the model that writes the answer. Any retry goes to the main model.
    main_model = config.agent_model(answerer.NAME)
    model = config.answer_model(prof["depth"]) if top_score >= config.ROUTER_MIN_SCORE else main_model
    if model != main_model:  # the default path calls the answerer exactly as before
        style_kw["model"] = model
        trace.add("router", _now(), f"{prof['depth']} question: {model}")

    def escalate() -> None:
        nonlocal model
        if model != main_model:
            model = main_model
            style_kw.pop("model", None)

    def deepen() -> list[dict] | None:
        """One wider search: more passages for the same question plus what earlier searches found.
        Returns None when that gives nothing new to read."""
        t = _now()
        more, _ = search_deep()
        pool: dict[str, dict] = {}
        for hits in searches:
            for h in hits:
                if h["rerank_score"] >= config.REFUSAL_THRESHOLD:
                    key = h["parent_content"]
                    if key not in pool or h["rerank_score"] > pool[key]["rerank_score"]:
                        pool[key] = h
        chosen, size = [], 0
        for h in sorted(pool.values(), key=lambda h: h["rerank_score"], reverse=True):
            if len(chosen) >= config.DEEP_MAX_PASSAGES or (chosen and size + len(h["parent_content"]) > config.DEEP_MAX_CHARS):
                continue
            chosen.append(h)
            size += len(h["parent_content"])
        known = {p["parent_content"] for p in reranked}
        if not chosen or {p["parent_content"] for p in chosen} <= known:
            trace.add("deeper", t, "no new passages")
            return None
        trace.add("deeper", t, f"{len(chosen)} passages (was {len(reranked)})")
        notes.append("deeper search")
        return chosen

    def search_deep() -> tuple[list[dict], float]:
        t = _now()
        hits = retriever.run(user, question, config.DEEP_TOP_K)
        score = max((h["rerank_score"] for h in hits), default=0.0)
        trace.add("retriever", t, f"deeper search, {len(hits)} passages, score {score:.3f}")
        searches.append(hits)
        return hits, score

    deep_done = False
    fit_retried = False
    while True:
        passages = [titled_passage(p["parent_content"], (p.get("metadata") or {}).get("title")) if config.SOURCE_TITLES_ENABLED
                    else p["parent_content"] for p in reranked]
        try:
            # 5. Answerer, with one retry if it forgot to cite.
            t = _now()
            try:
                answer = await answerer.run(question, passages, **style_kw)
            except LLMUnavailable:
                if model == main_model:
                    raise
                # The smaller model is not installed or not answering: the main model writes the answer instead.
                trace.add("router", _now(), f"{model} unavailable: main model answers")
                escalate()
                t = _now()
                answer = await answerer.run(question, passages, **style_kw)
            trace.add("answerer", t, "insufficient" if is_insufficient(answer) else f"drafted: {answer}")
            if is_insufficient(answer) and model != main_model:
                # The small model found nothing: the main model gets one try before the question is called unanswerable.
                escalate()
                t = _now()
                answer = await answerer.run(question, passages, **style_kw)
                trace.add("answerer", t, "main model: insufficient" if is_insufficient(answer) else f"main model: {answer}")
            # Hollow answer (only citation markers): no check below can judge it, so it never goes on.
            if not is_insufficient(answer) and is_hollow(answer):
                trace.add("validator", _now(), "hollow: no content besides citation markers")
                if model != main_model:
                    escalate()
                    t = _now()
                    answer = await answerer.run(question, passages, **style_kw)
                    trace.add("answerer", t, "main model: insufficient" if is_insufficient(answer) else f"main model: {answer}")
                if not is_insufficient(answer) and is_hollow(answer):
                    return finish("unverified", UNVERIFIED, top_score=top_score, model=model)
            # A smaller model's answer must use only figures from the passages and must address the question,
            # or the main model writes the answer instead.
            if model != main_model and not is_insufficient(answer):
                reason = None
                if unsupported_numbers(answer, passages):
                    reason = "number not found in the passages"
                else:
                    t = _now()
                    if not await fit_checker.run(question, answer):
                        reason = "answer does not address the question"
                        trace.add("validator", t, "fit: no")
                if reason:
                    trace.add("router", _now(), f"{reason}: main model answers")
                    escalate()
                    t = _now()
                    answer = await answerer.run(question, passages, **style_kw)
                    trace.add("answerer", t, "main model: insufficient" if is_insufficient(answer) else f"main model: {answer}")
            if not is_insufficient(answer) and not cited_numbers(answer, len(passages)):
                escalate()
                t = _now()
                answer = await answerer.run(question, passages, strict=True, **style_kw)
                trace.add("answerer", t, "retry: citations")

            # 6. Validator: every claim must be supported; regenerate a bounded number of times.
            if config.VALIDATOR_ENABLED:
                for attempt in range(config.VALIDATOR_MAX_RETRIES + 1):
                    if is_insufficient(answer) or not cited_numbers(answer, len(passages)):
                        break
                    # Plain-code rule first: every factual sentence must carry a citation. A sentence that the cited
                    # passage itself contains takes the citation of the sentence before it (checked in code).
                    answer = repair_neighbor_citation(answer, passages)
                    missing = uncited_sentences(answer, len(passages))
                    if missing:
                        trace.add("validator", _now(), f"uncited: {missing[0][:150]}")
                        if attempt == config.VALIDATOR_MAX_RETRIES:
                            return finish("unverified", UNVERIFIED, top_score=top_score, model=model)
                        escalate()
                        t = _now()
                        answer = await answerer.run(question, passages, strict=True, **style_kw,
                                                     feedback=f"this sentence has no source number: {missing[0]}")
                        trace.add("answerer", t, f"retry: citations: {answer}")
                        continue
                    t = _now()
                    ok, raw = await validator.run(question, answer, passages)
                    trace.add("validator", t, "SUPPORTED" if ok else f"UNSUPPORTED {raw[:300]}")
                    if ok:
                        # Supported is not the same as answering the question. Every answer is also checked for that,
                        # and one that misses the point is written again once. The check can only improve an answer
                        # that is already supported; if the second try still misses, it is shown as it is (it passed
                        # the validator), so this step can never turn an answer into a refusal.
                        if (config.FIT_CHECK_ALL and not fit_retried and model == main_model
                                and attempt < config.VALIDATOR_MAX_RETRIES):
                            t = _now()
                            fits = await fit_checker.run(question, answer)
                            trace.add("validator", t, f"fit: {'yes' if fits else 'no'}")
                            if not fits:
                                fit_retried = True
                                t = _now()
                                answer = await answerer.run(
                                    question, passages, strict=True, **style_kw,
                                    feedback="the answer must directly give what the question asks for, using only the sources")
                                trace.add("answerer", t, f"retry: fit: {answer}")
                                continue
                        break
                    if attempt == config.VALIDATOR_MAX_RETRIES:
                        return finish("unverified", UNVERIFIED, top_score=top_score, model=model)
                    escalate()
                    t = _now()
                    answer = await answerer.run(question, passages, strict=True, grounding=True, feedback=raw, **style_kw)
                    trace.add("answerer", t, f"retry: grounding: {answer}")
        except LLMUnavailable:
            finish("error", None, top_score=top_score, model=model)
            raise

        if is_insufficient(answer) and config.DEEP_SEARCH_ENABLED and not deep_done:
            deep_done = True
            wider = deepen()
            if wider:
                reranked = wider
                escalate()
                continue
        break

    if is_insufficient(answer):
        # The documents were close but silent. A plainly general question may still be answered, labelled.
        general_result = await general_path(question, prof, trace, finish, top_score)
        if general_result is not None:
            return general_result
        return finish("no_answer", NO_ANSWER, top_score=top_score, model=model)

    cited = cited_numbers(answer, len(passages))
    if not cited:
        return finish("unverified", UNVERIFIED, top_score=top_score, model=model)

    answer = strip_invalid_citations(answer, len(passages))
    sources = [
        {"number": n, "title": reranked[n - 1]["metadata"].get("title"),
         "document_id": reranked[n - 1].get("document_id"),
         "score": round(reranked[n - 1]["rerank_score"], 4)}
        for n in cited
    ]
    result = finish("answered", answer, sources, top_score, model)
    # The passage each citation points to, for the reader. Added after the audit record is written, so the audit
    # log never holds document text, and removed again before the reply is stored (see conversations.without_excerpts).
    result["sources"] = [
        dict(source, excerpt=" ".join(str(reranked[source["number"] - 1].get("parent_content", "")).split())[:EXCERPT_CHARS])
        for source in result["sources"]
    ]
    return result
