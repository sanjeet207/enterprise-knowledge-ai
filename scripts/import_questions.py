"""Turn a question sheet written by someone else (CSV) into an evaluation set.

Usage:
  python -m scripts.import_questions questions.csv            # writes evaluation/independent_set.json
  python -m scripts.evaluate --eval-set evaluation/independent_set.json --tag independent

The sheet format is described in evaluation/QUESTION_BRIEF.md. Mistakes in the sheet are listed with their row
number and nothing is written until the sheet is clean.
"""
import csv
import json
import sys
from pathlib import Path

USERS = {"analyst": "analyst@acme.test", "manager": "manager@acme.test", "director": "director@acme.test",
         "director_titan": "director_titan@acme.test", "partner_titan": "partner_titan@acme.test",
         "partner_outsider": "partner_outsider@acme.test"}
TYPES = {"answerable": "answerable", "blocked": "restricted", "not_in_documents": "unsupported",
         "general": "general", "off_topic": "off_topic"}
COLUMNS = ("asking_as", "type", "question", "document_title", "key_phrases", "secret_phrases")


def _split(value: str) -> list[str]:
    return [p.strip() for p in (value or "").split("|") if p.strip()]


def build_cases(rows: list[dict], titles: set[str]) -> tuple[list[dict], list[str]]:
    """Pure: sheet rows in, (evaluation cases, problems) out. Problems name the row (the sheet's first data row is 2)."""
    cases, problems = [], []
    for n, row in enumerate(rows, start=2):
        row = {k: (v or "").strip() for k, v in row.items() if k}
        if not any(row.values()):
            continue
        who, kind, question = row.get("asking_as", ""), row.get("type", ""), row.get("question", "")
        if who not in USERS:
            problems.append(f"row {n}: asking_as '{who}' is not one of {sorted(USERS)}")
        if kind not in TYPES:
            problems.append(f"row {n}: type '{kind}' is not one of {sorted(TYPES)}")
        if len(question) < 8:
            problems.append(f"row {n}: the question is empty or too short")
        if who not in USERS or kind not in TYPES or len(question) < 8:
            continue
        case = {"category": TYPES[kind], "user": USERS[who], "question": question}
        phrases, secrets = _split(row.get("key_phrases", "")), _split(row.get("secret_phrases", ""))
        if kind == "answerable":
            title = row.get("document_title", "")
            if title not in titles:
                problems.append(f"row {n}: document_title '{title}' is not a document title (copy it exactly)")
            if not phrases:
                problems.append(f"row {n}: an answerable question needs key_phrases (words the right answer must contain)")
            case.update(expect_doc=title, must_contain_any=phrases)
        elif kind == "general":
            if not phrases:
                problems.append(f"row {n}: a general question needs key_phrases")
            case.update(must_contain_any=phrases, forbidden=[])
        elif kind == "blocked":
            if not secrets:
                problems.append(f"row {n}: a blocked question needs secret_phrases (facts that must NOT appear)")
            case["forbidden"] = secrets
        else:
            case["forbidden"] = secrets
        cases.append(case)
    return cases, problems


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    from scripts.verify_access import DOCS  # imported here so the pure part has no dependencies
    titles = {d[1] for d in DOCS.values()}
    with open(sys.argv[1], newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            print(f"The sheet is missing columns: {missing}")
            return 1
        rows = list(reader)
    cases, problems = build_cases(rows, titles)
    if problems:
        print("Fix these first:\n  " + "\n  ".join(problems))
        return 1
    out = Path("evaluation/independent_set.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(cases, indent=1))
    kinds = {}
    for c in cases:
        kinds[c["category"]] = kinds.get(c["category"], 0) + 1
    print(f"Wrote {len(cases)} questions to {out}: {kinds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
