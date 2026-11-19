"""Compare the production search plan before and after ANALYZE, on data left by `scale_test --keep`."""
import re
import uuid

from app.services.vector_store import VectorStoreService

TENANT = "scaletest"


def short(lines):
    return [re.sub(r"\[[-0-9.,e ]{200,}\]", "[vector]", line) for line in lines]


def run(conn, label, embedding, question):
    sql = "EXPLAIN (ANALYZE, BUFFERS) " + VectorStoreService.SECURE_RRF_SQL
    args = (TENANT, 1, str(uuid.uuid4()), embedding, TENANT, embedding, question, TENANT, question, 60, 60, 5)
    plan = short([r[0] for r in conn.execute(sql, args).fetchall()])
    print(f"\n=== {label} ===")
    for line in plan:
        if any(k in line for k in ("Execution Time", "hnsw", "Index Scan using idx_children", "Seq Scan on child", "Bitmap", "Rows Removed")):
            print(line.strip())


def main():
    svc = VectorStoreService()
    with svc._connect() as conn:
        row = conn.execute("SELECT embedding, content FROM child_chunks WHERE tenant_id = %s LIMIT 1", (TENANT,)).fetchone()
        if not row:
            print("No scaletest data. Run: python -m scripts.scale_test --sizes 1000 --background 30000 --keep")
            return
        embedding, question = row[0], " ".join(row[1].split()[:8])
        for t in ("child_chunks", "parent_chunks"):
            r = conn.execute("SELECT last_analyze, last_autoanalyze, n_live_tup, last_autovacuum FROM pg_stat_user_tables WHERE relname = %s", (t,)).fetchone()
            print(f"{t}: last_analyze={r[0]} last_autoanalyze={r[1]} last_autovacuum={r[3]} live_rows={r[2]}")
        run(conn, "BEFORE ANALYZE", embedding, question)
        conn.commit()
        conn.autocommit = True
        conn.execute("ANALYZE child_chunks")
        conn.execute("ANALYZE parent_chunks")
        run(conn, "AFTER ANALYZE", embedding, question)
    import statistics, time
    times = []
    for _ in range(30):
        t = time.perf_counter()
        svc.secure_hybrid_rrf_search(TENANT, str(uuid.uuid4()), 1, question, top_k=5)
        times.append((time.perf_counter() - t) * 1000)
    times.sort()
    print(f"\n30 real searches (incl. query embedding): p50 {statistics.median(times):.0f} ms, p95 {times[28]:.0f} ms, max {times[-1]:.0f} ms")


if __name__ == "__main__":
    main()
