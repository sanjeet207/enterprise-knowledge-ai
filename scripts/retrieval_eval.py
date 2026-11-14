"""Measure retrieval alone: is the right document among the passages the search returns? No answer model is used,
so it takes about a minute and isolates the effect of the embedding model.

Usage: python -m scripts.retrieval_eval [--tag minilm]     (database needed; the server need not run)
Uses the answerable questions of tests/eval_set.json and evaluation/independent_set.json, exactly as typed
(typos included), asked as the demo user each question names. With --tag, writes evaluation/retrieval_<tag>.md.
"""
import argparse
import json
from pathlib import Path

from app import config
from app.agents.retriever import CANDIDATES, Retriever
from app.services import users
from app.services.vector_store import VectorStoreService

SETS = [("86-question set", "tests/eval_set.json"), ("27-question set", "evaluation/independent_set.json")]


def rank_of(title: str, hits: list[dict]) -> int | None:
    """1-based rank of the first passage from the expected document, or None."""
    for i, h in enumerate(hits, 1):
        if h["metadata"].get("title") == title:
            return i
    return None


def summarize(ranks: list[int | None]) -> dict:
    n = len(ranks) or 1
    return {f"hit@{k}": sum(1 for r in ranks if r and r <= k) / n for k in (1, 3, 5)} | {
        "mrr": sum(1 / r for r in ranks if r) / n}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="")
    args = parser.parse_args()
    store, retriever = VectorStoreService(), Retriever(VectorStoreService())
    cache: dict = {}
    lines = [f"# Retrieval check", "", f"Embedding: {config.EMBEDDING_PROVIDER} / {config.EMBEDDING_MODEL} / {config.EMBEDDING_DIM}", ""]
    for label, path in SETS:
        cases = [c for c in json.loads(Path(path).read_text()) if c["category"] == "answerable"]
        cand_ranks, final_ranks, misses = [], [], []
        for c in cases:
            if c["user"] not in cache:
                cache[c["user"]] = users.get_with_password_hash(c["user"])[0]
            user = cache[c["user"]]
            cands = store.secure_hybrid_rrf_search(tenant_id=user.tenant_id, user_id=user.id, user_level=user.level,
                                                   query=c["question"], top_k=CANDIDATES)
            final = retriever.run(user, c["question"], 5)
            cand_ranks.append(rank_of(c["expect_doc"], cands))
            r = rank_of(c["expect_doc"], final)
            final_ranks.append(r)
            if r is None or r > 1:
                misses.append(f"- rank {r or 'not found'}: {c['question'][:80]}  (expected {c['expect_doc']})")
        for stage, ranks in (("search (before rerank, top 10)", cand_ranks), ("after rerank (top 5)", final_ranks)):
            s = summarize(ranks)
            lines.append(f"{label}, {len(cases)} answerable questions, {stage}: "
                         f"right document first {s['hit@1']:.0%}, in top 3 {s['hit@3']:.0%}, in top 5 {s['hit@5']:.0%}, MRR {s['mrr']:.3f}")
        if misses:
            lines += ["", "Not ranked first after rerank:"] + misses
        lines.append("")
    print("\n".join(lines))
    if args.tag:
        Path("evaluation").mkdir(exist_ok=True)
        Path(f"evaluation/retrieval_{args.tag}.md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
