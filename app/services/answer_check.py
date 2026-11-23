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


_UNITS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
_TEENS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
          "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_NUMBER_WORD = re.compile(
    r"\b(?:(" + "|".join(_TENS) + r")(?:[- ](" + "|".join(_UNITS) + r"))?|(" + "|".join(_TEENS) + r")|(" + "|".join(_UNITS) + r"))\b",
    re.IGNORECASE)


_ANNOTATED = re.compile(_NUMBER_WORD.pattern + r" \(\d+\)", re.IGNORECASE)


def strip_number_annotations(text: str) -> str:
    """Undo annotate_number_words in a model's answer: "twenty-five (25) lakh" -> "twenty-five lakh".

    The models copy the digits they were shown. People should read the document's own wording, and every plain-code
    check (citation overlap, number check) compares against the original passages, so the answer is cleaned first.
    """
    return _ANNOTATED.sub(lambda m: m.group(0)[:m.group(0).rindex(" (")], text or "")


def annotate_number_words(text: str) -> str:
    """Put the digits after number words: "above twenty-five lakh" -> "above twenty-five (25) lakh".

    Shown to the models only, so that comparing "40" with a threshold written in words is possible; the stored
    passages and every plain-code check keep the original text. "one" is left alone (it is mostly not a figure).
    """
    def repl(m):
        tens, unit, teen, small = m.group(1), m.group(2), m.group(3), m.group(4)
        if tens:
            value = _TENS[tens.lower()] + (_UNITS[unit.lower()] if unit else 0)
        else:
            value = _TEENS[teen.lower()] if teen else _UNITS[small.lower()]
        if text[m.end():m.end() + 2] == " (":
            return m.group(0)
        return f"{m.group(0)} ({value})"
    return _NUMBER_WORD.sub(repl, text)


def repair_lead_citation(answer: str, source_count: int) -> str:
    """A Yes/No lead sentence with no citation, directly followed by a cited sentence, takes that sentence's citations.

    Models often write "No, you cannot do X. According to the policy [1], Y." The lead is the verdict on the
    explanation that follows, so the citation covers it; the claim validator still checks it against the sources.
    Nothing else is repaired, so the every-factual-sentence-needs-a-citation rule stays strict.
    """
    parts = re.split(r"(?<=[.!?])\s+", (answer or "").strip())
    for i in range(len(parts) - 1):
        lead, nxt = parts[i], parts[i + 1]
        if (re.match(r"(?i)(yes|no)\b", lead) and not cited_numbers(lead, source_count)
                and cited_numbers(nxt, source_count)):
            marks = "".join(f"[{k}]" for k in cited_numbers(nxt, source_count))
            end = re.search(r"[.!?]+$", lead)
            parts[i] = (lead[:end.start()] + " " + marks + lead[end.start():]) if end else f"{lead} {marks}"
    return " ".join(parts)


def repair_conclusion_citation(answer: str, source_count: int, min_overlap: float = 0.4) -> str:
    """An uncited sentence that restates the cited sentence just before it takes that sentence's citations.

    Models often write "Purchases above five lakh need three quotes [1]. Since this costs six lakh, you need three
    quotes." The second sentence applies the first to the user's case. Only a sentence that shares at least
    `min_overlap` of its content words with the cited sentence before it is repaired; the claim validator and the
    citation overlap check still judge it afterwards, and every other uncited sentence still fails.
    """
    parts = re.split(r"(?<=[.!?])\s+", (answer or "").strip())
    for i in range(1, len(parts)):
        prev, cur = parts[i - 1], parts[i]
        marks_prev = cited_numbers(prev, source_count)
        if cited_numbers(cur, source_count) or not marks_prev:
            continue
        a, b = set(_content_words(prev)), set(_content_words(cur))
        if len(b) >= 3 and len(a & b) / len(b) >= min_overlap:
            marks = "".join(f"[{k}]" for k in marks_prev)
            end = re.search(r"[.!?]+$", cur)
            parts[i] = (cur[:end.start()] + " " + marks + cur[end.start():]) if end else f"{cur} {marks}"
    return " ".join(parts)


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


def accept_refinement(original: str, refined: str, min_overlap: float = 0.7) -> str:
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
    if len(wanted & have) / len(wanted) < min_overlap:
        return original
    return text


def parse_refined_question(text: str, original: str, min_overlap: float = 0.7) -> str:
    """Read the refiner's JSON reply {"refined_question": "..."}; anything invalid keeps the original."""
    data = _load_json_object(text)
    value = data.get("refined_question") if data else None
    return accept_refinement(original, value, min_overlap) if isinstance(value, str) else original


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


_SCOPE_LEAD = re.compile(r"\b(depends?|varies|vary|differs?|different)\b", re.IGNORECASE)


def repair_neighbor_citation(answer: str, passages: list[str], min_overlap: float = 0.6) -> str:
    """An uncited sentence right after a cited one takes that citation if the cited passage really contains it.

    Models often write one cited sentence and then a second sentence from the same passage without repeating the
    number ("Claims are due in 30 days [2]. Later claims need the finance controller's approval."). The second
    sentence is checked in code: at least `min_overlap` of its content words must appear in a passage the sentence
    before it cites, so a sentence that is not in that passage stays uncited and still fails. The claim validator and
    the citation overlap check judge it afterwards. The answer is returned unchanged when nothing qualifies.
    """
    parts = re.split(r"(?<=[.!?])[ \t]+", (answer or "").strip())
    n = len(passages)
    changed = False
    for i in range(1, len(parts)):
        prev, cur = parts[i - 1], parts[i]
        marks_prev = cited_numbers(prev, n)
        if cited_numbers(cur, n) or not marks_prev:
            continue
        words = _content_words(cur)
        if len(words) < 3:
            continue
        best = max(len(words & _content_words(passages[k - 1])) / len(words) for k in marks_prev)
        if best >= min_overlap:
            marks = "".join(f"[{k}]" for k in marks_prev)
            end = re.search(r"[.!?]+$", cur)
            parts[i] = (cur[:end.start()] + " " + marks + cur[end.start():]) if end else f"{cur} {marks}"
            changed = True
    return " ".join(parts) if changed else answer


def uncited_sentences(answer: str, source_count: int, min_words: int = 3) -> list[str]:
    """Factual-looking sentences that carry no valid [n] citation. Plain code, no model.

    A sentence counts as factual if it has at least `min_words` content words, so short lead-ins and
    closers do not trigger it. A citation written after the full stop ("... week. [1]") is moved back
    onto its sentence first. The first sentence is also let through when it only announces that the answer
    varies ("This depends on your location.") has no figure in it, and the next sentence is cited: it asserts
    nothing that a source could confirm, and the facts that follow carry the citations.
    """
    text = re.sub(r"([.!?])\s*((?:\[\d+\]\s*)+)(?=\s|$)", r" \2\1", answer)
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", text)]
    sentences = [x for x in sentences if x]
    bad = []
    for i, sentence in enumerate(sentences):
        if cited_numbers(sentence, source_count):
            continue
        if (i == 0 and len(sentences) > 1 and not re.search(r"\d", sentence) and _SCOPE_LEAD.search(sentence)
                and cited_numbers(sentences[1], source_count)):
            continue
        if len(_content_words(sentence)) >= min_words:
            bad.append(sentence)
    return bad


def titled_passage(content: str, title: str | None) -> str:
    """The passage with its document title on a first line, so the model and the validator can tell two versions
    of one policy apart ("Travel and Expense Policy 2023" against "... 2025"). Without a title the passage is unchanged."""
    title = " ".join(str(title or "").split())[:150]
    return f"Document: {title}\n{content}" if title else content


def _title_stem(title: str) -> str:
    """A title with its year and version marks removed: "Travel Policy 2023" and "Travel Policy v2" share a stem."""
    t = re.sub(r"\bv(?:ersion)?\s*\d+(?:\.\d+)*\b|\d+", " ", str(title or "").lower())
    return " ".join(re.sub(r"[^a-z]+", " ", t).split())


def versioned_titles(titles: list[str | None]) -> set[str]:
    """Titles that differ from another retrieved title only by a year or version number. Only these need the title
    shown to the model, because their text is otherwise indistinguishable; for everything else the title line changed
    answer phrasing and cost a correct answer (see evaluation/HARDCORP_FINDINGS.md)."""
    clean = {" ".join(str(t or "").split()) for t in titles}
    clean.discard("")
    by_stem: dict[str, set[str]] = {}
    for t in clean:
        stem = _title_stem(t)
        if stem:
            by_stem.setdefault(stem, set()).add(t)
    return {t for group in by_stem.values() if len(group) > 1 for t in group}
