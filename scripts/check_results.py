"""Check that the numbers published in the README match the committed evaluation results.

Usage:  python -m scripts.check_results
Exit code 0 when every claim matches and there are no access leaks, 1 otherwise.

The README quotes accuracy figures. This recomputes them from the raw per-question results in evaluation/*.json,
so a published number cannot drift from the data behind it. It needs no database, no model and no network.
"""
import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent / "evaluation"

# What the README claims, per results file: category -> (passed, total); leaks must always be 0.
CLAIMS = {
    "newflow_results.json": {"total": 86, "answerable": (37, 37), "multi_part": (6, 6)},
    "newflow_hard_results.json": {"total": 45, "answerable": (22, 25)},
}


def summarise(rows: list[dict]) -> dict:
    """Pure: per-category (passed, total), overall counts and the number of leaks."""
    cats: dict[str, list[int]] = {}
    for r in rows:
        c = cats.setdefault(r["category"], [0, 0])
        c[0] += 1 if r.get("passed") else 0
        c[1] += 1
    return {"total": len(rows), "passed": sum(1 for r in rows if r.get("passed")),
            "leaks": sum(1 for r in rows if r.get("leaked")),
            "categories": {k: tuple(v) for k, v in cats.items()}}


def check(name: str, rows: list[dict], claim: dict) -> list[str]:
    """Pure: the problems found for one results file (empty list means it matches)."""
    s = summarise(rows)
    problems = []
    if s["leaks"]:
        problems.append(f"{name}: {s['leaks']} access leak(s), must be 0")
    if s["total"] != claim["total"]:
        problems.append(f"{name}: {s['total']} questions, README says {claim['total']}")
    for cat, want in claim.items():
        if cat == "total":
            continue
        got = s["categories"].get(cat)
        if got != want:
            problems.append(f"{name}: {cat} is {got}, README says {want}")
    return problems


def main() -> int:
    problems: list[str] = []
    for name, claim in CLAIMS.items():
        path = EVAL_DIR / name
        if not path.exists():
            problems.append(f"{name}: results file missing")
            continue
        s = summarise(json.loads(path.read_text()))
        print(f"{name}: {s['passed']}/{s['total']} passed, {s['leaks']} leaks")
        problems += check(name, json.loads(path.read_text()), claim)
    for p in problems:
        print("MISMATCH:", p)
    print("OK: published numbers match the data." if not problems else f"{len(problems)} problem(s).")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
