"""Kill-the-worker test: a document whose indexing died half way must never be searchable or counted as done.

It simulates a hard crash (an exception that the normal clean-up cannot catch, like a killed process) after the first
chunk of a multi-chunk document has been written, then runs the same job again and checks that exactly one complete
copy exists. Needs the database and the embedding model, not Ollama.

Usage: python -m scripts.crash_test
"""
import uuid

import psycopg

from app import config
from app.services import admin, ingest, users, versions
from app.services.vector_store import VectorStoreService


class SimulatedCrash(BaseException):
    """Not an Exception: the code's own 'except Exception' clean-up does not run, as when a process is killed."""


def count_chunks(tenant: str, document_id: str, status: str | None = None) -> int:
    sql = "SELECT COUNT(*) FROM parent_chunks WHERE tenant_id = %s AND document_id = %s"
    args = [tenant, document_id]
    if status:
        sql += " AND status = %s"
        args.append(status)
    with psycopg.connect(config.DATABASE_URL) as conn:
        return conn.execute(sql, args).fetchone()[0]


def main() -> int:
    found = users.get_with_password_hash("admin@acme.test")
    if not found:
        print("Run python -m scripts.seed_demo first.")
        return 1
    admin_user = found[0]
    text = " ".join(f"Sentence number {i} of the crash test document mentions the zebra protocol." for i in range(400))
    doc = str(uuid.uuid4())
    content_hash = "crash-test-" + doc
    store = ingest.vector_store
    real_add = store.add_parent_and_children
    calls = {"n": 0}

    def crashing_add(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise SimulatedCrash()
        return real_add(*args, **kwargs)

    results = []

    def check(label, ok):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {label}", flush=True)

    store.add_parent_and_children = crashing_add
    try:
        try:
            ingest.index_document(admin_user, doc, "Crash test document", text, 1, None, None, None, None, "published", content_hash)
            check("the simulated crash happened", False)
        except SimulatedCrash:
            check("the simulated crash happened", True)
    finally:
        store.add_parent_and_children = real_add

    partial = count_chunks(admin_user.tenant_id, doc)
    check("a half-written document exists on disk", partial >= 1)
    check("none of it is visible to search", count_chunks(admin_user.tenant_id, doc, "published") == 0)
    hits = ingest.vector_store.secure_hybrid_rrf_search(admin_user.tenant_id, admin_user.id, 1, "zebra protocol", top_k=5)
    check("search does not return it", all(h["document_id"] != doc for h in hits))

    result = ingest.index_document(admin_user, doc, "Crash test document", text, 1, None, None, None, None, "published", content_hash)
    total = count_chunks(admin_user.tenant_id, doc)
    check("the retry completes the document", result.get("parents_created", 0) >= 2)
    check("one complete copy, no duplicates", total == result["parents_created"])
    check("all of it is published now", count_chunks(admin_user.tenant_id, doc, "published") == total)

    admin.delete_document(admin_user.tenant_id, doc)
    check("cleaned up", count_chunks(admin_user.tenant_id, doc) == 0)
    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
