import sys
import uuid
from typing import Dict, List, Optional, Tuple

from app.security import hash_password
from app.services.chunker import HierarchicalChunker
from app.services.vector_store import VectorStoreService

DEMO_TENANTS = ("acme", "globex")
DEMO_PASSWORD = "DemoPass2026x"  # local development only

# Demo company: "Acme Financial Services" (fictional). All text is invented demo data.
# key: (tenant, title, classification_level, belongs_to_titan_deal_team, text)
DOCS = {
    # ---- Level 1: all employees ----
    "TRAVEL": ("acme", "Travel and Expense Policy", 1, False,
               "Employees may claim travel reimbursement for international conferences with written manager approval. "
               "Meal expenses on single-day trips are reimbursable up to the daily cap and need itemised receipts. "
               "Client entertainment is reimbursable up to the per-person limit and needs the client name and business purpose. "
               "Claims must be submitted within 30 days of travel (demo data)."),
    "LEAVE": ("acme", "Employee Leave Policy", 1, False,
              "Full-time employees receive twenty-four days of paid annual leave each year. Up to ten unused days may be "
              "carried forward to the next year. Leave of more than five consecutive days needs manager approval (demo data)."),
    "SECURITY": ("acme", "Information Security Policy", 1, False,
                 "Employees must use multi-factor authentication for all company systems. Customer data may not be copied to "
                 "personal devices or personal cloud storage. Suspected security incidents must be reported to the security "
                 "team within one hour (demo data)."),
    "CONDUCT": ("acme", "Code of Conduct and Whistleblower Policy", 1, False,
                "Employees must declare any conflict of interest to their manager before it affects a business decision. "
                "Gifts from clients worth more than 5000 rupees must be declined or reported to compliance. "
                "Concerns about misconduct can be reported anonymously through the ethics hotline, and retaliation against "
                "a person who reports in good faith is prohibited (demo data)."),
    "REMOTE": ("acme", "Remote and Hybrid Work Policy", 1, False,
               "Employees may work remotely up to three days a week with manager agreement. Work from outside the country "
               "needs written HR and security approval and is limited to thirty days a year. Company laptops must use the "
               "approved VPN when working remotely (demo data)."),
    # ---- Level 2: managers and above ----
    "KYC": ("acme", "KYC and AML Procedures", 2, False,
            "Customer onboarding requires identity verification and a sanctions screening before any account is opened. "
            "Transactions above the reporting threshold must be flagged for review in the monitoring system. "
            "Suspicious activity must be escalated to the compliance manager within 24 hours (demo data)."),
    "PERFREV": ("acme", "Performance Review and Promotion Process", 2, False,
                "Performance reviews run twice a year, in April and October. Managers rate each employee on a five point "
                "scale and submit ratings to the calibration committee. Promotion to the next grade requires two consecutive "
                "ratings of four or above and a sponsor from the director level (demo data)."),
    "VENDOR": ("acme", "Vendor Selection and Procurement Policy", 2, False,
               "Purchases above five lakh rupees require at least three written quotations. Vendors that handle customer data "
               "must pass a security assessment before a contract is signed. Contracts above twenty-five lakh rupees need "
               "director approval (demo data)."),
    "INCIDENT": ("acme", "Incident Response Runbook", 2, False,
                 "A security incident is classified as low, medium or high by the on-call security lead within thirty minutes. "
                 "High severity incidents trigger the crisis call and notification of the chief information security officer. "
                 "A written post-incident review is due within five working days (demo data)."),
    # ---- Level 3: directors and above ----
    "COMP": ("acme", "Executive Compensation Framework", 3, False,
             "The executive bonus pool is set annually by the board compensation committee. Executive compensation has a fixed "
             "component and a variable component linked to company revenue. Compensation reviews are confidential "
             "to directors and partners (demo data)."),
    "TURNOVER": ("acme", "Employee Attrition and Turnover Report", 3, False,
                 "Overall employee attrition for the year was 14 percent, down from 17 percent the year before. Attrition was "
                 "highest in the technology department at 21 percent and lowest in compliance at 6 percent. Exit interviews cite "
                 "career growth and compensation as the two main reasons for leaving (demo data)."),
    "RISK": ("acme", "Enterprise Risk Register", 3, False,
             "The top three enterprise risks are third party data breach, regulatory change in digital lending, and key "
             "person dependency in the payments team. The third party data breach risk is rated high and is owned by the "
             "chief information security officer. The register is reviewed every quarter (demo data)."),
    "TITAN": ("acme", "Project Titan Acquisition Valuation Memo", 3, True,
              "Project Titan valuation memo. The indicative enterprise valuation for Project Titan is 1.2 billion "
              "with a range of plus or minus ten percent. This memo is restricted to the Titan deal team (demo data)."),
    # ---- Level 4: partners and board ----
    "BOARD": ("acme", "Board Strategy Minutes", 4, False,
              "The board approved a plan to expand into two new regional markets over the next eighteen months. A decision on "
              "a possible acquisition of a payments company was deferred to the next quarter. These minutes are limited to "
              "partners and board members (demo data)."),
    # ---- Second company, to prove tenant isolation ----
    "GLOBEX": ("globex", "Globex Parental Leave Policy", 1, False,
               "Globex employees are entitled to sixteen weeks of paid parental leave, which may be taken in two blocks (demo data)."),
    "GLOBEXFIN": ("globex", "Globex Quarterly Financial Summary", 2, False,
                  "Globex quarterly revenue grew eight percent compared with the previous quarter. Operating costs were flat. "
                  "This summary is limited to managers and above (demo data)."),
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
    "globex_analyst": ("globex", 1),
    "globex_partner": ("globex", 4),
}
TITAN_TEAM = ("manager_titan", "director_titan", "partner_titan")


def can_see(user_key: str, doc_key: str) -> bool:
    """The access rule written down independently of the SQL: same tenant, a high enough
    level, and, for deal-team documents, membership of the deal team."""
    tenant, level = USERS[user_key]
    doc_tenant, _, doc_level, is_titan, _ = DOCS[doc_key]
    return doc_tenant == tenant and doc_level <= level and (not is_titan or user_key in TITAN_TEAM)


# One search query per document, used to sweep every user against every document.
TOPIC_QUERIES = {
    "TRAVEL": "travel reimbursement for international conference",
    "LEAVE": "annual leave carry forward",
    "SECURITY": "report a suspected security incident",
    "CONDUCT": "conflict of interest gifts from clients whistleblower",
    "REMOTE": "working remotely from abroad approval",
    "KYC": "customer onboarding identity verification sanctions screening",
    "PERFREV": "performance review promotion rating calibration",
    "VENDOR": "vendor quotations procurement approval",
    "INCIDENT": "incident severity classification post-incident review",
    "COMP": "executive bonus pool compensation",
    "TURNOVER": "employee attrition turnover rate by department",
    "RISK": "enterprise risk register top risks",
    "TITAN": "Project Titan valuation",
    "BOARD": "board strategy expansion acquisition decision",
    "GLOBEX": "parental leave weeks",
    "GLOBEXFIN": "quarterly revenue growth operating costs",
}

# Targeted checks: (who, query, expected top document or None)
CHECKS: List[Tuple[str, str, Optional[str]]] = [
    ("analyst", "travel reimbursement for international conference", "TRAVEL"),
    ("analyst", "client entertainment expense limit", "TRAVEL"),
    ("analyst", "annual leave carry forward", "LEAVE"),
    ("analyst", "report a suspected security incident", "SECURITY"),
    ("analyst", "employee attrition turnover rate by department", None),
    ("manager", "customer onboarding identity verification sanctions screening", "KYC"),
    ("manager", "performance review promotion rating calibration", "PERFREV"),
    ("director", "employee attrition turnover rate by department", "TURNOVER"),
    ("director", "executive bonus pool compensation", "COMP"),
    ("manager_titan", "Project Titan valuation", None),
    ("partner_outsider", "Project Titan valuation", None),
    ("director_titan", "Project Titan valuation", "TITAN"),
    ("partner_titan", "Project Titan valuation", "TITAN"),
    ("partner_outsider", "board strategy expansion acquisition decision", "BOARD"),
    ("globex_analyst", "quarterly revenue growth operating costs", None),
    ("globex_partner", "parental leave weeks", "GLOBEX"),
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
    password_hash = hash_password(DEMO_PASSWORD)
    with store._connect() as conn:
        conn.execute(
            "INSERT INTO engagements (id, tenant_id, name) VALUES (%s, %s, %s)",
            (titan_id, "acme", "Project Titan"),
        )
        for key, (tenant, level) in USERS.items():
            user_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO users (id, tenant_id, email, role_level, password_hash) VALUES (%s, %s, %s, %s, %s)",
                (user_id, tenant, f"{key}@{tenant}.test", level, password_hash),
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


def run_checks(store: VectorStoreService, users, titles: Dict[str, str]) -> Tuple[int, int]:
    """Returns (failures, total). Two kinds of check:
    1. Leak sweep: every user searches every document's topic and must never see a document
       they are not allowed to see.
    2. Targeted: selected searches must put the expected document first.
    """
    failures = 0
    total = 0

    def search(who: str, query: str) -> List[str]:
        user_id, tenant, level = users[who]
        hits = store.secure_hybrid_rrf_search(
            tenant_id=tenant, user_id=user_id, user_level=level, query=query, top_k=5
        )
        return [h["metadata"]["title"] for h in hits]

    title_to_key = {v: k for k, v in titles.items()}

    for who in USERS:
        for doc_key, query in TOPIC_QUERIES.items():
            total += 1
            found = search(who, query)
            leaked = [title_to_key[t] for t in found if not can_see(who, title_to_key[t])]
            if leaked:
                failures += 1
                print(f"FAIL  LEAK  {who} searching '{query[:40]}' saw {leaked}")

    print(f"Leak sweep: {total - failures}/{total} passed\n")

    for who, query, expect_top in CHECKS:
        total += 1
        found = search(who, query)
        leaked = [title_to_key[t] for t in found if not can_see(who, title_to_key[t])]
        top_ok = expect_top is None or (bool(found) and found[0] == titles[expect_top])
        ok = not leaked and top_ok
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {who:<17} {query[:44]:<46} -> {found[:3]}")
        if leaked:
            print(f"      LEAK: {who} could see {leaked}")
        if not top_ok:
            print(f"      expected top result: {titles[expect_top]}")
    return failures, total


def main() -> None:
    store = VectorStoreService()
    reset_demo(store)
    users, titles = seed(store)
    print("Seeded demo tenants, users, a deal team and documents.\n")
    failures, total = run_checks(store, users, titles)
    print(f"\n{total - failures}/{total} access checks passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
