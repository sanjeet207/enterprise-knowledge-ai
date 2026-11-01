"""Pure helpers that check a model answer. No I/O, so they are easy to unit test."""
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
