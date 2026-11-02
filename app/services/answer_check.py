"""Pure helpers that check a model answer. No I/O, so they are easy to unit test."""
import json
import re
from difflib import SequenceMatcher

INSUFFICIENT = "INSUFFICIENT_INFORMATION"
_CITATION = re.compile(r"\[(\d+)\]")


def is_insufficient(answer: str) -> bool:
    return not answer.strip() or INSUFFICIENT in answer


def cited_numbers(answer: str, source_count: int) -> list[int]:
    """Valid citation numbers (1..source_count) used in the answer, sorted."""
    found = {int(m) for m in _CITATION.findall(answer)}
    return sorted(n for n in found if 1 <= n <= source_count)


def strip_invalid_citations(answer: str, source_count: int) -> str:
    """Remove citation markers that point to a source that does not exist."""

    def keep(match: re.Match) -> str:
        return match.group(0) if 1 <= int(match.group(1)) <= source_count else ""

    return _CITATION.sub(keep, answer).strip()


def clean_rewrite(text: str, max_len: int = 200) -> str:
    """Make a model-written search query safe to use: first line only, no quotes or markup."""
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    line = line.strip().strip("\"'`*# ").strip()
    return line[:max_len]


def clean_rewrites(text: str, max_queries: int = 3, max_len: int = 200) -> list[str]:
    """Split a model-written list of search queries into clean, de-duplicated strings."""
    out: list[str] = []
    for raw in (text or "").splitlines():
        line = re.sub(r"^\s*(?:[-*\u2022]|\d+[.)])\s*", "", raw).strip().strip("\"'`*# ").strip()[:max_len]
        if line and line.lower() not in (q.lower() for q in out):
            out.append(line)
        if len(out) == max_queries:
            break
    return out


def parse_verdict(text: str) -> bool:
    """True only if the checker's first word is SUPPORTED. Anything unclear counts as not supported."""
    words = re.findall(r"[A-Za-z_]+", (text or "").upper())
    return bool(words) and words[0] == "SUPPORTED"


def accept_correction(original: str, corrected: str) -> str:
    """Use the model's corrected question only if it is plainly a spelling fix of the original.

    A model that answers the question, adds text or changes the meaning is ignored, so the corrector
    cannot be used to smuggle in a different question.
    """
    candidate = clean_rewrite(corrected, max_len=1000)
    if not candidate:
        return original
    if len(candidate) > 1.5 * len(original) + 20:
        return original
    if SequenceMatcher(None, original.lower(), candidate.lower()).ratio() < 0.6:
        return original
    return candidate


def _load_json_object(text: str) -> dict | None:
    try:
        data = json.loads(text or "")
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def parse_validation(text: str) -> tuple[bool, str]:
    """Read the validator's JSON reply: {"claims": [{"claim": "...", "supported": true/false}, ...]}.

    Fails closed: the answer counts as supported only if the reply is valid JSON, lists at least one claim,
    and every claim has `supported` exactly true. Returns (supported, short detail for the audit trace).
    """
    data = _load_json_object(text)
    claims = data.get("claims") if data else None
    if not isinstance(claims, list) or not claims:
        return False, "invalid reply"
    bad = []
    for item in claims:
        if not isinstance(item, dict) or not isinstance(item.get("claim"), str) or not isinstance(item.get("supported"), bool):
            return False, "invalid reply"
        if item["supported"] is not True:
            bad.append(item["claim"].strip())
    if bad:
        return False, ("; ".join(c for c in bad if c) or "claim not supported")[:140]
    return True, f"{len(claims)} claim(s) supported"


def parse_corrected_question(text: str, original: str) -> str:
    """Read the corrector's JSON reply {"corrected_question": "..."}; anything invalid keeps the original."""
    data = _load_json_object(text)
    value = data.get("corrected_question") if data else None
    return accept_correction(original, value) if isinstance(value, str) else original


def parse_plan(text: str, max_len: int = 150) -> tuple[str, str]:
    """Read the planner's JSON reply. Anything invalid, or a search with no usable query, means finish."""
    data = _load_json_object(text)
    if not data or data.get("action") != "search":
        return "finish", ""
    query = data.get("query")
    if not isinstance(query, str):
        return "finish", ""
    query = " ".join(query.split())[:max_len].strip()
    return ("search", query) if len(query) >= 3 else ("finish", "")


_STOPWORDS = frozenset(
    "a an and are as at be been by can do does for from has have how i if in into is it its may more must no not "
    "of on or our per than that the their them then there these they this to up was we were what when which who "
    "will with within you your also all any each may other such".split()
)


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())
    return {w.rstrip("s") if len(w) > 3 else w for w in words if w not in _STOPWORDS}


def citation_mismatches(answer: str, passages: list[str], threshold: float = 0.4) -> list[str]:
    """Sentences whose [n] citation points to a passage that does not contain most of the sentence's words.

    Plain code, no model: a sentence passes if at least one passage it cites shares >= `threshold` of its
    content words. Sentences with no valid citation are skipped (the validator agent judges those).
    """
    bad = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", answer):
        cited = cited_numbers(sentence, len(passages))
        if not cited:
            continue
        words = _content_words(_CITATION.sub(" ", sentence))
        if not words:
            continue
        best = max(len(words & _content_words(passages[n - 1])) / len(words) for n in cited)
        if best < threshold:
            bad.append(sentence.strip())
    return bad
