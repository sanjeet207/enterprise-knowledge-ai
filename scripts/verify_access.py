import sys
import uuid
from typing import Dict, List, Optional, Tuple

from app.services.chunker import HierarchicalChunker
from app.services.vector_store import VectorStoreService

DEMO_TENANTS = ("acme", "globex")

# key: (tenant, title, classification_level, belongs_to_titan_engagement, text)
DOCS = {
    "TRAVEL": ("acme", "Travel and Expense Policy", 1, False,
               "Employees may claim travel reimbursement for international conferences with written manager approval. "
               "Meal expenses on single-day trips are reimbursable up to the daily cap and need itemised receipts. "
               "Claims must be submitted within 30 days of travel (demo data)."),
    "TAX": ("acme", "Indirect Tax Compliance Guide", 2, False,
            "Input tax credit can be claimed only when the supplier has filed the return and the invoice appears in GSTR-2B. "
            "Reconcile GSTR-2B against the purchase register every month before filing GSTR-3B. "
            "Mismatches above the tolerance must be escalated to the indirect tax manager (demo data)."),
    "COMP": ("acme", "Director Compensation Framework", 3, False,
             "The director bonus pool is set annually by the partner committee. Director compensation has a fixed "
             "component and a variable component linked to practice revenue. Compensation reviews are confidential "
             "to directors and partners (demo data)."),
    "TITAN": ("acme", "Project Titan Valuation Memo", 3, True,
              "Project Titan valuation memo. The indicative enterprise valuation for Project Titan is 1.2 billion "
              "with a range of plus or minus ten percent. This memo is restricted to the Titan engagement team (demo data)."),
    "GLOBEX": ("globex", "Globex Parental Leave Policy", 1, False,
               "Globex employees are entitled to sixteen weeks of paid parental leave, which may be taken in two blocks (demo data)."),
}

# key: (tenant, role_level)
USERS = {
    "analyst": ("acme", 1),
    "manager": ("acme", 2),
    "director": ("acme", 3),
    "manager_titan": ("acme", 2),
    "director_titan": ("acme", 3),
    "partner_titan": ("acme", 4),
    "partner_outsider": ("acme", 4),
    "globex_partner": ("globex", 4),
}
TITAN_TEAM = ("manager_titan", "director_titan", "partner_titan")

TRAVEL_Q = "travel reimbursement for international conference"
TAX_Q = "input tax credit GSTR-2B reconciliation"
COMP_Q = "director bonus pool compensation"
TITAN_Q = "Project Titan valuation"

# (who, query, expected top document or None, documents they must NOT see)
CHECKS: List[Tuple[str, str, Optional[str], List[str]]] = [
    ("analyst", TRAVEL_Q, "TRAVEL", ["TAX", "COMP", "TITAN", "GLOBEX"]),
    ("analyst", TAX_Q, "TRAVEL", ["TAX", "COMP", "TITAN", "GLOBEX"]),
    ("manager", TAX_Q, "TAX", ["COMP", "TITAN", "GLOBEX"]),
    ("director", COMP_Q, "COMP", ["TITAN", "GLOBEX"]),
    ("manager_titan", TITAN_Q, None, ["COMP", "TITAN", "GLOBEX"]),
    ("partner_outsider", TITAN_Q, None, ["TITAN", "GLOBEX"]),
    ("director_titan", TITAN_Q, "TITAN", ["GLOBEX"]),
    ("partner_titan", TITAN_Q, "TITAN", ["GLOBEX"]),
    ("globex_partner", TRAVEL_Q, "GLOBEX", ["TRAVEL", "TAX", "COMP", "TITAN"]),
]


def reset_demo(store: VectorStoreService) -> None:
    tenants = list(DEMO_TENANTS)
    with store._connect() as conn:
        conn.execute("DELETE FROM parent_chunks WHERE tenant_id = ANY(%s)", (tenants,))
        conn.execute("DELETE FROM engagements WHERE tenant_id = ANY(%s)", (tenants,))
        conn.execute("DELETE FROM users WHERE tenant_id = ANY(%s)", (tenants,))


def seed(store: VectorStoreService) -> Tuple[Dict[str, Tuple[str, str, int]], Dict[str, str]]:
    titan_id = str(uuid.uuid4())
    users: Dict[str, Tuple[str, str, int]] = {}
    with store._connect() as conn:
        conn.execute(
            "INSERT INTO engagements (id, tenant_id, name) VALUES (%s, %s, %s)",
            (titan_id, "acme", "Project Titan"),
        )
        for key, (tenant, level) in USERS.items():
            user_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO users (id, tenant_id, email, role_level) VALUES (%s, %s, %s, %s)",
                (user_id, tenant, f"{key}@{tenant}.test", level),
            )
            users[key] = (user_id, tenant, level)
        for key in TITAN_TEAM:
            conn.execute(
                "INSERT INTO engagement_members (engagement_id, user_id) VALUES (%s, %s)",
                (titan_id, users[key][0]),
            )

    chunker = HierarchicalChunker()
    titles: Dict[str, str] = {}
    for key, (tenant, title, level, is_titan, text) in DOCS.items():
        document_id = str(uuid.uuid4())
        for item in chunker.chunk_document(text):
            store.add_parent_and_children(
                parent_id=str(uuid.uuid4()),
                tenant_id=tenant,
                document_id=document_id,
                parent_content=item["parent_content"],
                child_chunks=item["child_chunks"],
                classification_level=level,
                engagement_id=titan_id if is_titan else None,
                metadata={"title": title},
            )
        titles[key] = title
    return users, titles


def run_checks(store: VectorStoreService, users, titles: Dict[str, str]) -> int:
    failures = 0
    for who, query, expect_top, forbidden in CHECKS:
        user_id, tenant, level = users[who]
        hits = store.secure_hybrid_rrf_search(
            tenant_id=tenant, user_id=user_id, user_level=level, query=query, top_k=5
        )
        found = [h["metadata"]["title"] for h in hits]
        leaked = [key for key in forbidden if titles[key] in found]
        top_ok = expect_top is None or (bool(found) and found[0] == titles[expect_top])
        ok = not leaked and top_ok
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {who:<17} {query[:40]:<42} -> {found}")
        if leaked:
            print(f"      LEAK: {who} could see {leaked}")
        if not top_ok:
            print(f"      expected top result: {titles[expect_top]}")
    return failures


def main() -> None:
    store = VectorStoreService()
    reset_demo(store)
    users, titles = seed(store)
    print("Seeded demo tenants, users, an engagement team and documents.\n")
    failures = run_checks(store, users, titles)
    total = len(CHECKS)
    print(f"\n{total - failures}/{total} access checks passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
