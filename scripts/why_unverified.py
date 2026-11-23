"""Why did the system draft an answer and then not show it?  (database needed; reads the audit log only)

For every 'unverified' or 'no_answer' outcome logged for the Northwind company, print the validator and answer steps of its trace:
which check rejected the draft (no content, an uncited sentence, a number not found in the passages, the model validator, or the
question-fit check) and the short reason it gave. Nothing is changed. The point is to tell a validator that is right (the draft
really mixed an old and a new policy) from one that is too strict (the draft was correct and the check rejected it).

Usage:  python -m scripts.why_unverified                      Northwind, writes evaluation/WHY_UNVERIFIED.md
        python -m scripts.why_unverified acme.test gift      another company; only questions containing "gift"; prints, writes nothing
"""
import sys
from pathlib import Path


def main():
    from app.services.vector_store import VectorStoreService
    domain = sys.argv[1] if len(sys.argv) > 1 else "northwind.test"
    word = sys.argv[2] if len(sys.argv) > 2 else ""
    store = VectorStoreService()
    with store._connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT ON (query) created_at, user_email, query, outcome, top_score, trace FROM audit_log "
            "WHERE user_email LIKE %s AND query ILIKE %s AND outcome IN ('unverified','no_answer') ORDER BY query, created_at DESC",
            (f"%@{domain}", f"%{word}%")).fetchall()
    out = [f"# Why drafts were not shown ({domain}, latest run per question)", "",
           f"{len(rows)} questions. Validator and answer steps from the audit trace.", ""]
    for created, email, query, outcome, score, trace in sorted(rows, key=lambda r: (r[3], r[2])):
        out.append(f"## [{outcome}] {query}  (asked by {email.split('@')[0]}, best score {score if score is None else round(score, 3)})")
        steps = [s for s in (trace or []) if s.get("agent") in ("validator", "answerer", "router", "analysis", "refiner", "planner")]
        for s in steps:
            out.append(f"- {s.get('agent')}: {str(s.get('detail', ''))[:260]}")
        if not steps:
            out.append("- (no detail recorded in the trace)")
        out.append("")
    if len(sys.argv) == 1:
        Path("evaluation/WHY_UNVERIFIED.md").write_text("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
