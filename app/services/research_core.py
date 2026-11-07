"""Pure helpers for the research assistant: planning, citation renumbering and the checks on what a model writes."""
import json
import re
from typing import Dict, List, Optional, Tuple

from app.services import answer_check, compare

MAX_QUESTIONS = 5
MAX_QUESTION_CHARS = 200
_CITE = re.compile(r"\[(\d+)\]")


def parse_questions(raw: str, request: str) -> List[str]:
    """The research questions the planner proposed, cleaned. Falls back to the request itself (fail-safe)."""
    try:
        items = json.loads(raw).get("questions", [])
    except (ValueError, AttributeError, TypeError):
        items = []
    out: List[str] = []
    for item in items if isinstance(items, list) else []:
        text = " ".join(str(item).split())[:MAX_QUESTION_CHARS].strip()
        if len(text) >= 8 and text.lower() not in {q.lower() for q in out}:
            out.append(text)
    return out[:MAX_QUESTIONS] or [" ".join(request.split())[:MAX_QUESTION_CHARS]]


def renumber(answer: str, sources: List[dict], registry: Dict[str, int]) -> Tuple[str, List[int]]:
    """Rewrite a sub-answer's [n] markers to report-wide numbers, one number per document title."""
    local: Dict[int, int] = {}
    for s in sources:
        title = s.get("title") or "Untitled"
        if title not in registry:
            registry[title] = len(registry) + 1
        local[int(s["number"])] = registry[title]

    def swap(match: re.Match) -> str:
        n = int(match.group(1))
        return f"[{local[n]}]" if n in local else ""

    text = _CITE.sub(swap, answer).strip()
    used = sorted({int(n) for n in _CITE.findall(text)})
    return text, used


def verify_summary(summary: str, sections: List[str], source_count: int) -> Optional[str]:
    """None if the summary is acceptable, otherwise the reason it is not."""
    if not summary.strip():
        return "empty"
    if answer_check.uncited_sentences(summary, source_count):
        return "every sentence needs a citation"
    if not answer_check.cited_numbers(summary, source_count):
        return "no valid citation"
    if any(int(n) > source_count for n in _CITE.findall(summary)):
        return "cites a source that does not exist"
    findings = " ".join(sections)
    stray = compare.numbers(_CITE.sub("", summary)) - compare.numbers(_CITE.sub("", findings))
    if stray:
        return "contains figures not in the findings: " + ", ".join(sorted(stray))
    return None


def _norm(text: str) -> str:
    return " ".join(_CITE.sub("", text).lower().split())


def valid_conflicts(raw: str, sections: List[str]) -> List[Dict[str, str]]:
    """Possible inconsistencies the model flagged, kept only when both quoted statements really appear in the findings."""
    try:
        items = json.loads(raw).get("conflicts", [])
    except (ValueError, AttributeError, TypeError):
        return []
    haystack = [_norm(s) for s in sections]
    out = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        a, b = _norm(str(item.get("statement_a", ""))), _norm(str(item.get("statement_b", "")))
        if a and b and a != b and any(a in h for h in haystack) and any(b in h for h in haystack):
            out.append({"topic": str(item.get("topic", ""))[:120], "statement_a": str(item["statement_a"])[:400],
                        "statement_b": str(item["statement_b"])[:400]})
    return out[:3]
