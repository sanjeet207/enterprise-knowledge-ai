"""Which part of the search actually helps? Same questions, same access rules, one change at a time.

Usage: python -m scripts.retrieval_ablation       (database needed; no answer model, no server; about two minutes)
       python -m scripts.retrieval_ablation --hard  the same variants on the Northwind corpus (load it first: python -m scripts.hardcorp_seed);
                                                    adds a table by question kind and writes evaluation/RETRIEVAL_ABLATION_HARD.md

Variants (all use the production access filter; they differ only in how passages are ranked):
  vector only        meaning search alone
  keyword only       word search alone
  hybrid (RRF)       both, fused by reciprocal rank (what the application searches with)
  hybrid + rerank    cross-encoder order only          (RERANK_BLEND=none)
  hybrid + rerank, guarded                              (RERANK_BLEND=guard)
  hybrid + rerank, fused with the search order          (RERANK_BLEND=rrf, the application default)

Questions: every answerable question of tests/eval_set.json and evaluation/independent_set.json, as typed (typos included),
asked as the demo user each names. Each has exactly one right document, so recall@k is "right document within the first k".
Writes evaluation/RETRIEVAL_ABLATION.md and evaluation/retrieval_ablation.json.
"""
import json
import math
import statistics
import time
from pathlib import Path

KS = (1, 3, 5, 10)
SETS = [("86-question set", "tests/eval_set.json"), ("27-question set", "evaluation/independent_set.json")]
HARD_SETS = [("Northwind hard corpus", "evaluation/hardcorp_set.json")]
REPORT, DATA = "evaluation/RETRIEVAL_ABLATION.md", "evaluation/retrieval_ablation.json"
HARD_REPORT, HARD_DATA = "evaluation/RETRIEVAL_ABLATION_HARD.md", "evaluation/retrieval_ablation_hard.json"


def rank_of(title, hits):
    for i, h in enumerate(hits, 1):
        if h["metadata"].get("title") == title:
            return i
    return None


def ndcg_at(rank, k=10):
    """One right document, so the ideal score is 1 and NDCG is 1/log2(rank+1) when it is in the first k."""
    return 1.0 / math.log2(rank + 1) if rank and rank <= k else 0.0


def percentile(values, p):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))]


def summarize(ranks, millis):
    n = len(ranks) or 1
    out = {f"recall@{k}": sum(1 for r in ranks if r and r <= k) / n for k in KS}
    out["mrr"] = sum(1 / r for r in ranks if r) / n
    out["ndcg@10"] = sum(ndcg_at(r) for r in ranks) / n
    out["not_found"] = sum(1 for r in ranks if r is None)
    out["p50_ms"] = statistics.median(millis) if millis else 0.0
    out["p95_ms"] = percentile(millis, 95)
    return out


def compare(base, other):
    """How many questions the variant ranks better / worse / the same as the baseline (None counts as worst)."""
    big = 10 ** 6
    better = sum(1 for a, b in zip(base, other) if (b or big) < (a or big))
    worse = sum(1 for a, b in zip(base, other) if (b or big) > (a or big))
    return better, worse, len(base) - better - worse


def main():
    import sys
    hard = "--hard" in sys.argv
    sets = HARD_SETS if hard else SETS
    report, data = (HARD_REPORT, HARD_DATA) if hard else (REPORT, DATA)
    from app import config
    from app.services import reranker, users
    from app.services.vector_store import VectorStoreService

    base_sql = VectorStoreService.SECURE_RRF_SQL
    vec_term, txt_term = "COALESCE(1.0 / (%s + v.rank), 0.0)", "COALESCE(1.0 / (%s + t.rank), 0.0)"
    assert vec_term in base_sql and txt_term in base_sql, "the search SQL changed; update this script"

    class VectorOnly(VectorStoreService):
        SECURE_RRF_SQL = base_sql.replace(txt_term, "0.0 * " + txt_term)

    class KeywordOnly(VectorStoreService):
        SECURE_RRF_SQL = base_sql.replace(vec_term, "0.0 * " + vec_term)

    stores = {"vector": VectorOnly(), "keyword": KeywordOnly(), "hybrid": VectorStoreService()}
    cases, owners = [], {}
    for label, path in sets:
        for c in json.loads(Path(path).read_text()):
            if c["category"] == "answerable":
                cases.append((label, c))
                owners.setdefault(c["user"], users.get_with_password_hash(c["user"])[0])

    def search(kind, user, query):
        hits = stores[kind].secure_hybrid_rrf_search(tenant_id=user.tenant_id, user_id=user.id, user_level=user.level,
                                                     query=query, top_k=10)
        return [h for h in hits if h["rrf_score"] > 0] if kind != "hybrid" else hits

    def with_rerank(mode):
        def run(user, query):
            hits = search("hybrid", user, query)
            old = config.RERANK_BLEND
            config.RERANK_BLEND = mode
            try:
                return reranker.rerank_passages(query, hits, top_k=10) if hits else []
            finally:
                config.RERANK_BLEND = old
        return run

    variants = {
        "vector only": lambda u, q: search("vector", u, q),
        "keyword only": lambda u, q: search("keyword", u, q),
        "hybrid (RRF)": lambda u, q: search("hybrid", u, q),
        "hybrid + rerank (reranker order only)": with_rerank("none"),
        "hybrid + rerank (guarded)": with_rerank("guard"),
        "hybrid + rerank, fused with search order (default)": with_rerank("rrf"),
    }
    warm_user, warm_q = owners[cases[0][1]["user"]], cases[0][1]["question"]
    for run in variants.values():  # load models once, so timings measure searching, not start-up
        run(warm_user, warm_q)

    ranks = {name: {} for name in variants}
    kinds = {}
    millis = {name: {} for name in variants}
    for label, c in cases:
        user = owners[c["user"]]
        for name, run in variants.items():
            start = time.perf_counter()
            hits = run(user, c["question"])
            millis[name].setdefault(label, []).append((time.perf_counter() - start) * 1000)
            ranks[name].setdefault(label, []).append(rank_of(c["expect_doc"], hits))
        kinds.setdefault(label, []).append(c.get("kind", ""))

    groups = [(label, label) for label, _ in sets] + ([("both sets together", None)] if len(sets) > 1 else [])
    lines = ["# Retrieval ablation", "",
             f"Embedding: {config.EMBEDDING_PROVIDER} / {config.EMBEDDING_MODEL}. One right document per question; recall@k means "
             "the right document is within the first k passages. Latency is the whole retrieval step (query embedding, SQL, rerank).", ""]
    results = {}
    for title, label in groups:
        keys = [label] if label else [lab for lab, _ in sets]
        n = sum(len(ranks["vector only"][k]) for k in keys)
        lines += [f"## {title} ({n} answerable questions)", "",
                  "| Variant | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | NDCG@10 | p50 ms | p95 ms | Not found |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        base_ranks = [r for k in keys for r in ranks["hybrid (RRF)"][k]]
        for name in variants:
            rs = [r for k in keys for r in ranks[name][k]]
            ms = [m for k in keys for m in millis[name][k]]
            s = summarize(rs, ms)
            results[f"{title} | {name}"] = s
            lines.append(f"| {name} | " + " | ".join(f"{s[f'recall@{k}']:.0%}" for k in KS) +
                         f" | {s['mrr']:.3f} | {s['ndcg@10']:.3f} | {s['p50_ms']:.0f} | {s['p95_ms']:.0f} | {s['not_found']} |")
        lines += ["", "Against plain hybrid search, question by question (better / worse / same rank):", ""]
        for name in variants:
            if name == "hybrid (RRF)":
                continue
            b, w, same = compare(base_ranks, [r for k in keys for r in ranks[name][k]])
            lines.append(f"- {name}: {b} better, {w} worse, {same} same")
        lines.append("")
        if hard:
            kind_list = [k for key in keys for k in kinds[key]]
            lines += ["By kind of question (recall@1 / recall@5; each cell is the number of questions of that kind):", "",
                      "| Kind | n | " + " | ".join(variants) + " |", "|---|---|" + "---|" * len(variants)]
            for kind in sorted(set(kind_list)):
                cells = []
                for name in variants:
                    rs = [r for key in keys for r, k in zip(ranks[name][key], kinds[key]) if k == kind]
                    cells.append(f"{sum(1 for r in rs if r == 1)}/{sum(1 for r in rs if r and r <= 5)}")
                lines.append(f"| {kind} | {kind_list.count(kind)} | " + " | ".join(cells) + " |")
            lines.append("")
    lines += ["## How to read this", "",
              "- With about fifty questions, a difference of one or two questions is noise. Look for gaps that hold in both sets and "
              "across several columns.",
              "- Parent-child retrieval (search small chunks, hand the model the whole section) is not a ranking choice and is not "
              "compared here. Query rewriting needs a model and is measured separately (see `evaluation/refiner_experiment`).",
              "- Depth: the recall@1, 3, 5 and 10 columns are the top-K sweep. The application keeps 5 passages after reranking.", ""]
    Path(report).write_text("\n".join(lines))
    Path(data).write_text(json.dumps(results, indent=2))
    print("\n".join(lines))
    print("Report: " + report)


if __name__ == "__main__":
    main()
