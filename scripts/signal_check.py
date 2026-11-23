"""Is there a better relevance signal than the reranker score?  (database needed; no answer model, no server)

The refusal gate uses the reranker score. The threshold sweep showed that score is about 0.000 for several everyday-wording questions
whose right document search ranks first to third. This script adds a second candidate signal, the cosine similarity between the question
and the closest passage the asker may read, and prints both for every question, split into questions that should be answered and
questions that should be refused. It changes nothing. Read it as: do the two groups separate on the new signal, where they do not on the old?

Usage:  python -m scripts.signal_check     writes evaluation/SIGNAL_CHECK.md
"""
import json
from pathlib import Path

SETS = [("Northwind (hard corpus)", "evaluation/hardcorp_set.json"), ("86-question demo set", "tests/eval_set.json"),
        ("27-question demo set", "evaluation/independent_set.json")]
SHOULD_ANSWER = {"answerable", "multi_part"}
SHOULD_REFUSE = {"restricted", "off_topic", "injection", "unsupported"}
SQL = """
    SELECT 1 - MIN(c.embedding <=> %s) FROM child_chunks c
    JOIN parent_chunks p ON c.parent_id = p.id
    WHERE p.tenant_id = %s AND p.status = 'published' AND p.classification_level <= %s
      AND (p.engagement_id IS NULL OR p.engagement_id IN (SELECT engagement_id FROM engagement_members WHERE user_id = %s))
"""
THRESHOLDS = [0.2, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55]


def main():
    from app.agents.retriever import Retriever
    from app.services import users
    from app.services.embedder import embed_texts
    from app.services.vector_store import VectorStoreService

    store = VectorStoreService()
    retriever = Retriever(store)
    owners = {}
    out = ["# Relevance signal check", "",
           "Per question: reranker score (what the gate uses today) and cosine similarity to the closest readable passage. "
           "Raw question text, no typo correction or rewriting, so typo questions look worse than in the application.", ""]
    for label, path in SETS:
        rows = []
        for c in json.loads(Path(path).read_text()):
            kind = "answer" if c["category"] in SHOULD_ANSWER else "refuse" if c["category"] in SHOULD_REFUSE else None
            if not kind:
                continue
            if c["user"] not in owners:
                owners[c["user"]] = users.get_with_password_hash(c["user"])[0]
            u = owners[c["user"]]
            hits = retriever.run(u, c["question"], 5)
            rerank = max((h["rerank_score"] for h in hits), default=0.0)
            emb = embed_texts([c["question"]], kind="query")[0]
            with store._connect() as conn:
                row = conn.execute(SQL, (emb, u.tenant_id, u.level, u.id)).fetchone()
            cos = float(row[0]) if row and row[0] is not None else 0.0
            rows.append((kind, rerank, cos, c["question"], c["category"]))
        ans = [r for r in rows if r[0] == "answer"]
        ref = [r for r in rows if r[0] == "refuse"]
        out += [f"## {label}", "", "Gate today: reranker >= 0.1. Alternative: pass if reranker >= 0.1 OR cosine >= T.", "",
                "| T | Should-answer blocked | Should-refuse passing |", "|---|---|---|"]
        out.append(f"| (today, reranker only) | {sum(1 for r in ans if r[1] < 0.1)} of {len(ans)} | {sum(1 for r in ref if r[1] >= 0.1)} of {len(ref)} |")
        for t in THRESHOLDS:
            out.append(f"| {t} | {sum(1 for r in ans if r[1] < 0.1 and r[2] < t)} of {len(ans)} | {sum(1 for r in ref if r[1] >= 0.1 or r[2] >= t)} of {len(ref)} |")
        out += ["", "Should-answer questions the gate blocks today (reranker, cosine):", ""]
        out += [f"- {r[1]:.4f}  cos {r[2]:.3f}  {r[3][:70]}" for r in sorted(ans, key=lambda r: r[1]) if r[1] < 0.1]
        out += ["", "Should-refuse questions, highest cosine first (reranker, cosine):", ""]
        out += [f"- {r[1]:.4f}  cos {r[2]:.3f}  [{r[4]}] {r[3][:60]}" for r in sorted(ref, key=lambda r: -r[2])[:8]]
        out.append("")
    Path("evaluation/SIGNAL_CHECK.md").write_text("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
