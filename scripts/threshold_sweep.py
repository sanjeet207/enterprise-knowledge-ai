"""Where does the refusal threshold sit relative to the real relevance scores?  (database needed; no answer model, no server)

The application refuses a question when the best reranker score among the passages the person may read is below REFUSAL_THRESHOLD.
That number was chosen on the small demo company. This script asks the same retriever the application uses (same access filter, same
reranker) for every question of three sets and shows the best score of each, split into questions that should be answered and
questions that should be refused (restricted, unsupported, off-topic, injection). It then counts, for several thresholds, how many
questions of each kind would pass the gate. Nothing is changed; it only measures.

Usage:  python -m scripts.threshold_sweep          writes evaluation/THRESHOLD_SWEEP.md
(The Northwind corpus must be loaded: python -m scripts.hardcorp_seed. The demo companies: python -m scripts.seed_demo.)
"""
import json
from pathlib import Path

SETS = [("Northwind (hard corpus)", "evaluation/hardcorp_set.json"), ("86-question demo set", "tests/eval_set.json"),
        ("27-question demo set", "evaluation/independent_set.json")]
SHOULD_ANSWER = {"answerable", "multi_part"}
SHOULD_REFUSE = {"restricted", "off_topic", "injection", "unsupported"}
THRESHOLDS = [0.005, 0.01, 0.02, 0.05, 0.1, 0.15, 0.25]


def main():
    from app.agents.retriever import Retriever
    from app.services import users
    from app.services.vector_store import VectorStoreService

    retriever = Retriever(VectorStoreService())
    owners = {}
    lines = ["# Refusal threshold sweep", "",
             "Best reranker score of the passages the asker may read, per question. The gate refuses below the threshold "
             "(application default 0.1). Measured with the application's own retriever; no answer model involved.", ""]
    for label, path in SETS:
        answer, refuse = [], []
        for c in json.loads(Path(path).read_text()):
            kind = "answer" if c["category"] in SHOULD_ANSWER else "refuse" if c["category"] in SHOULD_REFUSE else None
            if not kind:
                continue
            if c["user"] not in owners:
                owners[c["user"]] = users.get_with_password_hash(c["user"])[0]
            hits = retriever.run(owners[c["user"]], c["question"], 5)
            score = max((h["rerank_score"] for h in hits), default=0.0)
            (answer if kind == "answer" else refuse).append((score, c["question"], c["category"]))
        answer.sort()
        refuse.sort(reverse=True)
        lines += [f"## {label}", f"{len(answer)} questions that should be answered, {len(refuse)} that should be refused.", "",
                  "| Threshold | Should-answer refused at the gate | Should-refuse that pass the gate |", "|---|---|---|"]
        for t in THRESHOLDS:
            lines.append(f"| {t} | {sum(1 for s, _, _ in answer if s < t)} of {len(answer)} | {sum(1 for s, _, _ in refuse if s >= t)} of {len(refuse)} |")
        lines += ["", "Lowest scores among questions that should be answered:", ""]
        lines += [f"- {s:.4f}  {q[:80]}" for s, q, _ in answer[:8]]
        lines += ["", "Highest scores among questions that should be refused:", ""]
        lines += [f"- {s:.4f}  [{cat}] {q[:80]}" for s, q, cat in refuse[:8]]
        lines.append("")
    Path("evaluation/THRESHOLD_SWEEP.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
