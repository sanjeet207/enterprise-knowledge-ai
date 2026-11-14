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
        return False, ("; ".join(c for c in bad if c) or "claim not supported")[:300]
    return True, f"{len(claims)} claim(s) supported"


def parse_route(text: str) -> str:
    """Read the router's JSON reply {"route": "general" | "company" | "decline"}.

    Fails closed: anything else counts as "company", which is refused.
    """
    data = _load_json_object(text)
    route = data.get("route") if data else None
    return route if route in ("general", "decline") else "company"


def parse_general_check(text: str) -> tuple[bool, str]:
    """Read the general-answer checker's JSON reply. Fails closed: the answer passes only when it answers the
    question (true), makes no company-specific claim (false) and states no uncertain specifics (false)."""
    data = _load_json_object(text)
    if not data:
        return False, "invalid reply"
    answers, company, uncertain = (data.get("answers_the_question"), data.get("company_specific"),
                                   data.get("uncertain_specifics"))
    if not all(isinstance(v, bool) for v in (answers, company, uncertain)):
        return False, "invalid reply"
    if answers and not company and not uncertain:
        return True, "ok"
    reason = data.get("reason") if isinstance(data.get("reason"), str) else ""
    if not answers:
        reason = reason or "does not answer the question"
    elif company:
        reason = reason or "makes claims about a specific company"
    else:
        reason = reason or "states a precise fact it cannot be sure of"
    return False, reason.strip()[:300]


def parse_corrected_question(text: str, original: str) -> str:
    """Read the corrector's JSON reply {"corrected_question": "..."}; anything invalid keeps the original."""
    data = _load_json_object(text)
    value = data.get("corrected_question") if data else None
    return accept_correction(original, value) if isinstance(value, str) else original


def is_hollow(answer: str) -> bool:
    """True if the answer has no real content once citation markers like [1] are removed (a model that writes only "[1]"); even "Yes [1]" has content."""
    words = re.findall(r"[A-Za-z]{2,}", re.sub(r"\[\d+\]", " ", answer or ""))
    return not words


def parse_fit(text: str) -> bool:
    """Read the fit checker's JSON reply {"answers_question": bool}. Anything unreadable counts as yes (fail open)."""
    data = _load_json_object(text)
    value = data.get("answers_question") if data else None
    return value if isinstance(value, bool) else True


def unsupported_numbers(answer: str, passages: list[str]) -> list[str]:
    """Figures in the answer that appear in none of the passages (citation markers like [1] are ignored).

    Plain code. A figure the model wrote as digits but the document wrote in words ("3" / "three") also shows up here,
    which is harmless: it only sends the question to the larger model.
    """
    text = re.sub(r"\[\d+\]", " ", answer)
    wanted = set(re.findall(r"\d+(?:[.,]\d+)*", text))
    have = set(re.findall(r"\d+(?:[.,]\d+)*", " ".join(passages)))
    norm = lambda n: n.replace(",", "")  # noqa: E731
    have_norm = {norm(h) for h in have}
    return sorted(n for n in wanted if norm(n) not in have_norm)


def accept_refinement(original: str, refined: str) -> str:
    """Return the refined question only if plain code agrees it kept the meaning; otherwise the original.

    Rules: one line, not an answer; no number added or dropped; not much longer than a clear question needs; and
    most of the original's content words are still there (so no part of a multi-part question is lost).
    """
    text = " ".join((refined or "").replace('"', " ").split())
    if not text or "[" in text or "\n" in (refined or "").strip():
        return original
    if text.lower().startswith(("answer:", "the answer", "yes,", "no,")):
        return original
    if len(text.split()) > max(45, 3 * len(original.split()) + 15):
        return original
    numbers = lambda s: sorted(re.findall(r"\d+(?:[.,]\d+)?", s))  # noqa: E731
    if numbers(text) != numbers(original):
        return original
    wanted = {w[:4] for w in _content_words(original)}
    if not wanted:
        return original
    have = {w[:4] for w in _content_words(text)}
    if len(wanted & have) / len(wanted) < 0.7:
        return original
    return text


def parse_refined_question(text: str, original: str) -> str:
    """Read the refiner's JSON reply {"refined_question": "..."}; anything invalid keeps the original."""
    data = _load_json_object(text)
    value = data.get("refined_question") if data else None
    return accept_refinement(original, value) if isinstance(value, str) else original


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
    "will with within you your also all any each may other such ok okay".split()
)


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())
    return {w.rstrip("s") if len(w) > 3 else w for w in words if w not in _STOPWORDS}


def citation_mismatches(answer: str, passages: list[str], threshold: float = 0.4, question: str = "") -> list[str]:
    """Sentences whose [n] citation points to a passage that does not contain most of the sentence's words.

    Plain code, no model: a sentence passes if at least one passage it cites shares >= `threshold` of its
    content words. Sentences with no valid citation are skipped (the validator agent judges those).

    Words the question itself used are not counted against the sentence: a correct yes/no answer repeats the
    question ("No, it is not okay to keep customer files in your personal Dropbox [1]") and the document never
    mentions Dropbox. What is left, the words that carry the claim, must still be found in the cited passage, so
    a wrong claim ("Yes ...") still fails. A sentence made only of question words is left to the validator.
    """
    asked = _content_words(question)
    bad = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", answer):
        cited = cited_numbers(sentence, len(passages))
        if not cited:
            continue
        words = _content_words(_CITATION.sub(" ", sentence)) - asked
        if not words:
            continue
        best = max(len(words & _content_words(passages[n - 1])) / len(words) for n in cited)
        if best < threshold:
            bad.append(sentence.strip())
    return bad


def uncited_sentences(answer: str, source_count: int, min_words: int = 3) -> list[str]:
    """Factual-looking sentences that carry no valid [n] citation. Plain code, no model.

    A sentence counts as factual if it has at least `min_words` content words, so short lead-ins and
    closers do not trigger it. A citation written after the full stop ("... week. [1]") is moved back
    onto its sentence first.
    """
    text = re.sub(r"([.!?])\s*((?:\[\d+\]\s*)+)(?=\s|$)", r" \2\1", answer)
    bad = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        sentence = sentence.strip()
        if not sentence or cited_numbers(sentence, source_count):
            continue
        if len(_content_words(sentence)) >= min_words:
            bad.append(sentence)
    return bad
