"""Scale test for retrieval: speed, recall and access control as the corpus grows.

Builds a synthetic corpus in its own tenant ("scaletest"), in steps (default 100, 1,000 and 10,000 documents), and at each
step measures, using the same secure hybrid search the application uses:

  * search time (median and 95th percentile), split into query embedding and search
  * recall: is the right document among the top 5 for questions about "needle" documents hidden in the noise
  * leaks: restricted needle documents must never appear for a level-1 user (the run fails if one does)
  * how many results come back (fewer than 5 means the access filter is starving the vector search)
  * throughput and errors with 1, 4 and 8 simultaneous searches

The noise documents are generated from templates with invented names and numbers, so they look like the needles. It
measures the retrieval step only, not the model that writes the answer. The results describe this machine, this
database and this synthetic corpus; they are not a claim about any real company's data.

Usage: python -m scripts.scale_test [--sizes 100,1000,10000] [--keep]
Report: evaluation/SCALE_REPORT.md and evaluation/scale_results.json
"""
import argparse
import json
import platform
import random
import statistics
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TENANT = "scaletest"
DEPARTMENTS = ["Finance", "Legal", "Procurement", "Operations", "Compliance", "Risk", "Treasury", "Audit", "Facilities", "Payroll"]
TOPICS = ["travel", "vendor", "expense", "security", "leave", "onboarding", "records", "approval", "reporting", "training"]
UNITS = ["days", "lakh rupees", "hours", "working days", "percent", "quotations"]
ROLES = ["manager", "director", "partner", "finance head", "department lead", "committee"]
SYLLABLES = ["zor", "van", "mel", "quix", "tor", "bel", "dru", "san", "ket", "lin", "fro", "gam", "hex", "nar", "pol", "ryn"]
RESTRICTED_LEVEL = 4
VISIBLE_LEVEL = 1


def invented_word(rng: random.Random) -> str:
    """A made-up word that appears in no real text, so a needle cannot be found by general knowledge."""
    return "".join(rng.choice(SYLLABLES) for _ in range(3)).capitalize()


def make_needles(count: int, restricted: bool, seed: int) -> list[dict]:
    """Documents with one unique fact each, and the question that should find them."""
    rng = random.Random(seed + (1000 if restricted else 0))
    needles = []
    for i in range(count):
        word, dept = invented_word(rng) + str(i), rng.choice(DEPARTMENTS)
        number, unit, role = rng.randint(3, 99), rng.choice(UNITS), rng.choice(ROLES)
        fact = f"The {word} allowance for the {dept} department is {number} {unit}, approved by the {role}."
        needles.append({
            "id": str(uuid.uuid4()), "level": RESTRICTED_LEVEL if restricted else VISIBLE_LEVEL, "restricted": restricted,
            "children": [fact, f"This rule is reviewed every year by the {dept} department."],
            "question": f"What is the {word} allowance for the {dept} department?",
        })
    return needles


def make_noise(count: int, seed: int, start: int = 0, restricted_share: float = 0.3) -> list[dict]:
    """Noise documents that resemble the needles but state other facts. Some are restricted, like real corpora."""
    docs = []
    for i in range(start, start + count):
        rng = random.Random(seed * 1_000_003 + i)
        children = []
        for _ in range(3):
            sentences = []
            for _ in range(rng.randint(2, 3)):
                sentences.append(
                    f"The {rng.choice(TOPICS)} {rng.choice(['rule', 'limit', 'procedure', 'allowance'])} for the "
                    f"{rng.choice(DEPARTMENTS)} department is {rng.randint(3, 99)} {rng.choice(UNITS)}, "
                    f"approved by the {rng.choice(ROLES)} under code {invented_word(rng)}{rng.randint(0, 999)}."
                )
            children.append(" ".join(sentences))
        level = RESTRICTED_LEVEL if rng.random() < restricted_share else VISIBLE_LEVEL
        docs.append({"id": str(uuid.uuid4()), "level": level, "restricted": level == RESTRICTED_LEVEL, "children": children})
    return docs


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))]


def insert(svc, docs: list[dict]) -> float:
    """Embed and insert documents in one batch; returns seconds taken."""
    from psycopg.types.json import Jsonb
    from app.services.embedder import embed_texts
    start = time.perf_counter()
    texts = [c for d in docs for c in d["children"]]
    vectors = embed_texts(texts)
    with svc._connect() as conn, conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO parent_chunks (id, tenant_id, document_id, content, classification_level, engagement_id, metadata, status) "
            "VALUES (%s, %s, %s, %s, %s, NULL, %s, 'published')",
            [(d["id"], TENANT, d["id"], " ".join(d["children"]), d["level"], Jsonb({"title": "synthetic"})) for d in docs],
        )
        rows, k = [], 0
        for d in docs:
            for index, child in enumerate(d["children"]):
                rows.append((d["id"], TENANT, d["id"], index, child, vectors[k]))
                k += 1
        cur.executemany(
            "INSERT INTO child_chunks (parent_id, tenant_id, document_id, chunk_index, content, embedding) VALUES (%s, %s, %s, %s, %s, %s)",
            rows,
        )
    return time.perf_counter() - start


def cleanup(svc) -> None:
    with svc._connect() as conn:
        conn.execute("DELETE FROM parent_chunks WHERE tenant_id = %s", (TENANT,))


def measure(svc, needles: list[dict], user_level: int, user_id: str) -> dict:
    from app.services.embedder import embed_texts
    embed_ms, total_ms, found, returned, leaks, eligible = [], [], 0, [], 0, 0
    restricted_ids = {n["id"] for n in needles if n["restricted"]}
    for n in needles:
        t0 = time.perf_counter()
        embed_texts([n["question"]], kind="query")
        t1 = time.perf_counter()
        hits = svc.secure_hybrid_rrf_search(TENANT, user_id, user_level, n["question"], top_k=5)
        t2 = time.perf_counter()
        embed_ms.append((t1 - t0) * 1000)
        total_ms.append((t2 - t1) * 1000)
        returned.append(len(hits))
        ids = {h["document_id"] for h in hits}
        if user_level < RESTRICTED_LEVEL:
            leaks += len(ids & restricted_ids)
        # Recall counts only needles this user may see; finding a restricted one would be a leak, not a hit.
        if not (n["restricted"] and user_level < RESTRICTED_LEVEL):
            eligible += 1
            if n["id"] in ids:
                found += 1
    return {
        "questions": len(needles), "answerable": eligible, "recall_at_5": found / eligible if eligible else 0.0,
        "search_ms_p50": statistics.median(total_ms), "search_ms_p95": percentile(total_ms, 95),
        "embed_ms_p50": statistics.median(embed_ms), "mean_results": statistics.mean(returned), "leaks": leaks,
    }


def concurrency(svc, needles: list[dict], workers: int, total: int = 120) -> dict:
    user_id = str(uuid.uuid4())
    questions = [n["question"] for n in needles if not n["restricted"]] or ["x"]
    errors, times = 0, []

    def one(i: int) -> None:
        nonlocal errors
        t0 = time.perf_counter()
        try:
            svc.secure_hybrid_rrf_search(TENANT, user_id, VISIBLE_LEVEL, questions[i % len(questions)], top_k=5)
            times.append((time.perf_counter() - t0) * 1000)
        except Exception:
            errors += 1

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, range(total)))
    wall = time.perf_counter() - start
    return {"workers": workers, "searches": total, "errors": errors, "per_second": total / wall if wall else 0.0,
            "p50_ms": statistics.median(times) if times else 0.0, "p95_ms": percentile(times, 95)}


def table_sizes(svc) -> dict:
    with svc._connect() as conn:
        row = conn.execute(
            "SELECT pg_total_relation_size('child_chunks'), pg_total_relation_size('parent_chunks'), "
            "(SELECT count(*) FROM child_chunks WHERE tenant_id = %s)", (TENANT,),
        ).fetchone()
    return {"child_mb": round(row[0] / 1e6, 1), "parent_mb": round(row[1] / 1e6, 1), "scale_chunks": row[2]}


def write_report(results: list[dict], path: Path) -> None:
    lines = ["# Scale test", "",
             f"Machine: {platform.platform()}, Python {platform.python_version()}. Synthetic corpus in its own tenant; retrieval only, no answer model.",
             "Needles are unique facts hidden among noise documents that look like them; 30% of the noise is restricted (level 4). A level-1 user is also asked about restricted needles: finding one is a leak, and recall counts only the questions that user may see.", "",
             "| Documents | Chunks | Insert (docs/s) | Search p50 / p95 (ms) | Query embed p50 (ms) | Right document in top 5 | Mean results returned | Restricted leaks | Table size (MB) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        m = r["level1"]
        lines.append(f"| {r['documents']:,} | {r['sizes']['scale_chunks']:,} | {r['insert_docs_per_s']:.0f} | {m['search_ms_p50']:.0f} / {m['search_ms_p95']:.0f} | "
                     f"{m['embed_ms_p50']:.0f} | {m['recall_at_5']:.0%} | {m['mean_results']:.1f} | {m['leaks']} | {r['sizes']['child_mb']} |")
    lines += ["", "Level-4 user searching for the restricted needles (should find them):", "",
              "| Documents | Right document in top 5 | Search p50 (ms) |", "|---|---|---|"]
    for r in results:
        lines.append(f"| {r['documents']:,} | {r['level4']['recall_at_5']:.0%} | {r['level4']['search_ms_p50']:.0f} |")
    lines += ["", "Simultaneous searches (level-1 user):", "", "| Documents | Workers | Searches/s | p50 / p95 (ms) | Errors |", "|---|---|---|---|---|"]
    for r in results:
        for c in r["concurrency"]:
            lines.append(f"| {r['documents']:,} | {c['workers']} | {c['per_second']:.1f} | {c['p50_ms']:.0f} / {c['p95_ms']:.0f} | {c['errors']} |")
    lines += ["", "Recall below 100% or a mean result count below 5 at larger sizes means the access filter leaves the vector search "
              "with too few candidates (filtered approximate search), not that a model is wrong."]
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="100,1000,10000", help="comma-separated document counts, run in order")
    parser.add_argument("--needles", type=int, default=30, help="visible needles; half as many restricted ones are added")
    parser.add_argument("--keep", action="store_true", help="leave the synthetic tenant in the database")
    args = parser.parse_args()
    sizes = [int(s) for s in args.sizes.split(",")]

    from app.services.vector_store import VectorStoreService
    svc = VectorStoreService()
    cleanup(svc)
    visible = make_needles(args.needles, restricted=False, seed=1)
    restricted = make_needles(max(1, args.needles // 2), restricted=True, seed=1)
    needles = visible + restricted
    user1, user4 = str(uuid.uuid4()), str(uuid.uuid4())
    results, have, rate = [], 0, 0.0
    try:
        insert(svc, needles)
        have = len(needles)
        for size in sizes:
            todo = max(0, size - have)
            started = time.perf_counter()
            for offset in range(0, todo, 500):
                insert(svc, make_noise(min(500, todo - offset), seed=7, start=have + offset))
            if todo:
                rate = todo / (time.perf_counter() - started)
            have = max(have, size)
            with svc._connect() as conn:
                conn.execute("ANALYZE child_chunks")
            print(f"== {size:,} documents ==", flush=True)
            level1 = measure(svc, needles, VISIBLE_LEVEL, user1)
            level4 = measure(svc, restricted, RESTRICTED_LEVEL, user4)
            conc = [concurrency(svc, needles, w) for w in (1, 4, 8)]
            results.append({"documents": size, "insert_docs_per_s": rate, "sizes": table_sizes(svc),
                            "level1": level1, "level4": level4, "concurrency": conc})
            print(f"   recall@5 {level1['recall_at_5']:.0%}, p50 {level1['search_ms_p50']:.0f} ms, results {level1['mean_results']:.1f}, leaks {level1['leaks']}", flush=True)
    finally:
        if not args.keep:
            cleanup(svc)
    out = Path("evaluation")
    out.mkdir(exist_ok=True)
    (out / "scale_results.json").write_text(json.dumps(results, indent=2))
    write_report(results, out / "SCALE_REPORT.md")
    print("Report: evaluation/SCALE_REPORT.md")
    return 1 if any(r["level1"]["leaks"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
