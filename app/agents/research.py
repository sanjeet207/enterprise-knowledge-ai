"""Research assistant orchestrator: plain code that runs a bounded, multi-step investigation.

Permissions: there is no separate path to documents. Every research question goes through the same orchestrator and
SQL-filtered retriever as a normal chat question, as the same user, so the assistant can never read more than the person can.
A step that finds nothing is reported as an evidence gap. Nothing the models write is shown unless code has checked it.
"""
import time
from typing import Any, Dict, List

from app.agents import orchestrator, research_agents
from app.services import audit, metrics, question_profile, research_core
from app.services.llm import LLMUnavailable

GAP_REASON = "No usable evidence was found in the documents available to you."
BUDGET_SECONDS = 300


class ResearchRefused(ValueError):
    """The request cannot be researched."""


async def run_research(user, request: str, retriever, budget: float = BUDGET_SECONDS) -> Dict[str, Any]:
    started = time.perf_counter()
    request = " ".join(request.split())
    if question_profile.OVERRIDE_PATTERN.search(request):
        raise ResearchRefused("That request tries to change the assistant's rules, so it was not researched.")

    steps: List[dict] = []
    t = time.perf_counter()
    questions = await research_agents.plan(request)
    steps.append({"step": "plan", "ms": int((time.perf_counter() - t) * 1000), "detail": " | ".join(questions)})

    registry: Dict[str, int] = {}
    sections, gaps = [], []
    for q in questions:
        if time.perf_counter() - started > budget:
            gaps.append({"question": q, "reason": "Not researched: the time limit for one report was reached."})
            continue
        t = time.perf_counter()
        result = await orchestrator.answer_question(user, q, 3, retriever)  # same user, same access rules
        steps.append({"step": "research", "ms": int((time.perf_counter() - t) * 1000), "detail": f"{result['outcome']}: {q}"})
        if result["outcome"] != "answered":
            gaps.append({"question": q, "reason": GAP_REASON})  # refused and not-found look the same on purpose
            continue
        text, used = research_core.renumber(result["answer"], result["sources"], registry)
        sections.append({"question": q, "answer": text, "sources": used})

    texts = [s["answer"] for s in sections]
    limitations: List[str] = []
    summary, inconsistencies = None, []
    if texts:
        t = time.perf_counter()
        summary = await research_agents.summarise(texts, len(registry))
        steps.append({"step": "summary", "ms": int((time.perf_counter() - t) * 1000), "detail": "accepted" if summary else "rejected twice"})
        if summary is None:
            limitations.append("A checked executive summary could not be produced, so none is shown. The findings below are complete.")
    if len(texts) >= 2:
        t = time.perf_counter()
        inconsistencies = await research_agents.find_conflicts(texts)
        steps.append({"step": "consistency", "ms": int((time.perf_counter() - t) * 1000), "detail": f"{len(inconsistencies)} flagged"})
    if gaps:
        limitations.append(f"{len(gaps)} of {len(questions)} research question(s) could not be answered from the documents available to you.")
    if not sections:
        limitations.append("No findings: the documents available to you do not cover this request.")

    report = {
        "request": request, "title": request[:100], "summary": summary, "sections": sections, "gaps": gaps,
        "inconsistencies": inconsistencies, "limitations": limitations,
        "sources": [{"number": n, "title": title} for title, n in sorted(registry.items(), key=lambda kv: kv[1])],
        "status": "draft", "elapsed_s": round(time.perf_counter() - started, 1), "steps": steps,
    }
    outcome = "report" if sections and not gaps else "report_partial"
    audit.log_event(user, "[research] " + request, outcome, None, report["sources"], summary, None,
                    int((time.perf_counter() - started) * 1000), None, steps)
    metrics.inc("research_reports_total", outcome=outcome)
    return report
