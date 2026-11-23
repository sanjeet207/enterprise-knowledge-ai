"""Does a more forgiving keyword search help? Nothing in the application is changed by this script.

Usage: python -m scripts.keyword_experiment       (database needed; no answer model, no server; about a minute)

The keyword half of the search uses plainto_tsquery: EVERY word of the question must appear in one passage. A question with one
word the document never uses finds nothing. The experiment swaps in an OR query (any word may match, passages with more matching
words rank higher) and compares, on two kinds of question:
  paraphrase    tests/eval_set.json + evaluation/independent_set.json: everyday wording, typos included
  exact terms   evaluation/exact_term_set.json: short searches for a specific phrase, code or name a document contains

Variants: vector only; keyword AND (today); keyword OR; hybrid with AND keyword (today); hybrid with OR keyword.
Writes evaluation/KEYWORD_EXPERIMENT.md and evaluation/keyword_experiment.json.
"""
import json
import time
from pathlib import Path

from scripts.retrieval_ablation import KS, SETS, compare, rank_of, summarize

AND_QUERY = "plainto_tsquery('english', %s)"
# Any word of the question may match: letters and digits only, joined with " | " (safe for to_tsquery whatever was typed).
OR_QUERY = "to_tsquery('english', regexp_replace(btrim(regexp_replace(%s, '[^[:alnum:]]+', ' ', 'g')), ' +', ' | ', 'g'))"
EXACT_SET = ("exact terms", "evaluation/exact_term_set.json")
VEC_TERM, TXT_TERM = "COALESCE(1.0 / (%s + v.rank), 0.0)", "COALESCE(1.0 / (%s + t.rank), 0.0)"


def or_sql(base_sql: str) -> str:
    """The search SQL with the keyword half using the OR query. Same placeholders, same order, so the same parameters work."""
    assert base_sql.count(AND_QUERY) == 2, "the search SQL changed; update this script"
    return base_sql.replace(AND_QUERY, OR_QUERY)


def main():
    from app.services import users
    from app.services.vector_store import VectorStoreService

    base = VectorStoreService.SECURE_RRF_SQL
    assert VEC_TERM in base and TXT_TERM in base, "the search SQL changed; update this script"
    or_base = or_sql(base)

    def store(sql):
        class Variant(VectorStoreService):
            SECURE_RRF_SQL = sql
        return Variant()

    stores = {
        "vector only": (store(base.replace(TXT_TERM, "0.0 * " + TXT_TERM)), True),
        "keyword AND (today)": (store(base.replace(VEC_TERM, "0.0 * " + VEC_TERM)), True),
        "keyword OR": (store(or_base.replace(VEC_TERM, "0.0 * " + VEC_TERM)), True),
        "hybrid, AND keyword (today)": (store(base), False),
        "hybrid, OR keyword": (store(or_base), False),
    }
    sets = SETS + [EXACT_SET]
    cases, owners = [], {}
    for label, path in sets:
        for c in json.loads(Path(path).read_text()):
            if c["category"] == "answerable":
                cases.append((label, c))
                owners.setdefault(c["user"], users.get_with_password_hash(c["user"])[0])

    def run(name, user, query):
        svc, drop_zero = stores[name]
        hits = svc.secure_hybrid_rrf_search(tenant_id=user.tenant_id, user_id=user.id, user_level=user.level, query=query, top_k=10)
        return [h for h in hits if h["rrf_score"] > 0] if drop_zero else hits

    first = cases[0][1]
    for name in stores:  # load the embedding model once, so timings measure searching
        run(name, owners[first["user"]], first["question"])

    ranks = {n: {} for n in stores}
    millis = {n: {} for n in stores}
    for label, c in cases:
        user = owners[c["user"]]
        for name in stores:
            start = time.perf_counter()
            hits = run(name, user, c["question"])
            millis[name].setdefault(label, []).append((time.perf_counter() - start) * 1000)
            ranks[name].setdefault(label, []).append(rank_of(c["expect_doc"], hits))

    groups = [("paraphrase questions (both sets)", [lab for lab, _ in SETS]), ("exact-term searches", [EXACT_SET[0]])]
    lines = ["# Keyword search experiment", "",
             "Only the keyword half changes: AND (every word must appear, today) against OR (any word may match, more matching words "
             "rank higher). Same access filter, same questions, no reranker.", ""]
    results = {}
    for title, keys in groups:
        n = sum(len(ranks["vector only"][k]) for k in keys)
        lines += [f"## {title} ({n} questions)", "",
                  "| Variant | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | NDCG@10 | p50 ms | p95 ms | Not found |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        base_ranks = [r for k in keys for r in ranks["hybrid, AND keyword (today)"][k]]
        for name in stores:
            rs = [r for k in keys for r in ranks[name][k]]
            s = summarize(rs, [m for k in keys for m in millis[name][k]])
            results[f"{title} | {name}"] = s
            lines.append(f"| {name} | " + " | ".join(f"{s[f'recall@{k}']:.0%}" for k in KS) +
                         f" | {s['mrr']:.3f} | {s['ndcg@10']:.3f} | {s['p50_ms']:.0f} | {s['p95_ms']:.0f} | {s['not_found']} |")
        lines += ["", "Against today's hybrid search, question by question (better / worse / same rank):", ""]
        for name in stores:
            if name != "hybrid, AND keyword (today)":
                b, w, same = compare(base_ranks, [r for k in keys for r in ranks[name][k]])
                lines.append(f"- {name}: {b} better, {w} worse, {same} same")
        lines.append("")
    lines += ["## How to read this", "",
              "- The demo company has 14 short documents, so even meaning search alone finds almost everything. A real company has "
              "thousands of long ones, where exact words (policy numbers, names, codes) matter more. These numbers show the direction, "
              "not the size of the effect.",
              "- Fifteen exact-term questions: one question is about 7 points. Treat a difference of one or two as noise.", ""]
    Path("evaluation/KEYWORD_EXPERIMENT.md").write_text("\n".join(lines))
    Path("evaluation/keyword_experiment.json").write_text(json.dumps(results, indent=2))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
