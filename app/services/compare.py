"""Compare two documents sentence by sentence in plain code. The model only summarises what this finds."""
import difflib
import re
from typing import Dict, List

SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])")
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
MIN_PAIR_SIMILARITY = 0.45
MAX_CHANGES = 60


def split_sentences(text: str) -> List[str]:
    return [s.strip() for s in SENTENCE.split(" ".join((text or "").split())) if s.strip()]


def numbers(text: str) -> set:
    return {n.rstrip(".,") for n in NUMBER.findall(text or "")}


def _pair(old: List[str], new: List[str]) -> List[Dict[str, str]]:
    """Inside one replaced block, pair each old sentence with its most similar new one."""
    out, free = [], list(range(len(new)))
    for before in old:
        best, best_ratio = None, MIN_PAIR_SIMILARITY
        for j in free:
            ratio = difflib.SequenceMatcher(None, before.lower(), new[j].lower()).ratio()
            if ratio > best_ratio:
                best, best_ratio = j, ratio
        if best is None:
            out.append({"type": "removed", "before": before, "after": ""})
        else:
            free.remove(best)
            out.append({"type": "changed", "before": before, "after": new[best]})
    out.extend({"type": "added", "before": "", "after": new[j]} for j in free)
    return out


def diff(old_text: str, new_text: str) -> Dict:
    a, b = split_sentences(old_text), split_sentences(new_text)
    changes, unchanged = [], 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            unchanged += i2 - i1
        elif op == "delete":
            changes += [{"type": "removed", "before": s, "after": ""} for s in a[i1:i2]]
        elif op == "insert":
            changes += [{"type": "added", "before": "", "after": s} for s in b[j1:j2]]
        else:
            changes += _pair(a[i1:i2], b[j1:j2])
    return {"changes": changes[:MAX_CHANGES], "total_changes": len(changes), "unchanged": unchanged,
            "sentences": {"old": len(a), "new": len(b)}}


def changes_prompt(changes: List[Dict[str, str]]) -> str:
    lines = []
    for i, c in enumerate(changes, start=1):
        lines.append(f"{i}. {c['type'].upper()}\n   before: {c['before'] or '(none)'}\n   after: {c['after'] or '(none)'}")
    return "<changes>\n" + "\n".join(lines) + "\n</changes>"


def numbers_grounded(summary: str, changes: List[Dict[str, str]]) -> bool:
    """Every number in the summary must appear in the changes it describes (no invented figures)."""
    allowed = set()
    for c in changes:
        allowed |= numbers(c["before"]) | numbers(c["after"])
    return numbers(summary) <= allowed | {str(i) for i in range(1, len(changes) + 1)}
