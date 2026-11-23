"""Clear the activity of a DEMO tenant (questions, conversations, access requests) so the Administration page starts clean
after evaluation and load runs. People, teams and documents are kept.

It refuses any tenant that is not a known demo tenant, and does nothing without --yes. The change history is kept and
records that this happened.

Usage: python -m scripts.reset_demo_activity --tenant acme --yes
"""
import argparse

import psycopg
from psycopg.types.json import Jsonb

from app.config import DATABASE_URL

DEMO_TENANTS = ("acme", "globex", "scaletest")


def reset(tenant: str) -> dict:
    if tenant not in DEMO_TENANTS:
        raise SystemExit(f"Refusing: '{tenant}' is not a demo tenant ({', '.join(DEMO_TENANTS)})")
    with psycopg.connect(DATABASE_URL) as conn:
        counts = {
            "audit_rows": conn.execute("DELETE FROM audit_log WHERE tenant_id = %s", (tenant,)).rowcount,
            "conversations": conn.execute("DELETE FROM conversations WHERE tenant_id = %s", (tenant,)).rowcount,
            "access_requests": conn.execute("DELETE FROM access_requests WHERE tenant_id = %s", (tenant,)).rowcount,
        }
        conn.execute("INSERT INTO admin_events (tenant_id, actor_id, actor_email, action, target, detail) "
                     "VALUES (%s, '00000000-0000-0000-0000-000000000000', 'system', 'demo.reset', %s, %s)",
                     (tenant, tenant, Jsonb(counts)))
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--yes", action="store_true", help="really delete")
    args = parser.parse_args()
    if args.tenant not in DEMO_TENANTS:
        raise SystemExit(f"Refusing: '{args.tenant}' is not a demo tenant ({', '.join(DEMO_TENANTS)})")
    if not args.yes:
        raise SystemExit("Nothing deleted. Add --yes to clear this demo tenant's activity.")
    print(reset(args.tenant))


if __name__ == "__main__":
    main()
