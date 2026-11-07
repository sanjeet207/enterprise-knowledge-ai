import psycopg

from app.config import DATABASE_URL
from app.security import hash_password
from app.services.vector_store import VectorStoreService
from scripts.verify_access import DEMO_TENANTS, reset_demo, seed

DEMO_PASSWORD = "DemoPass2026x"  # local development only


def main() -> None:
    store = VectorStoreService()
    reset_demo(store)
    users, _ = seed(store)
    password_hash = hash_password(DEMO_PASSWORD)
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(
            "UPDATE users SET password_hash = %s WHERE tenant_id = ANY(%s)",
            (password_hash, list(DEMO_TENANTS)),
        )
        # The knowledge-management team of each company: publishes documents, manages people and teams.
        # Level 1 on purpose: administering the portal does not grant the right to read restricted documents.
        for tenant in DEMO_TENANTS:
            conn.execute(
                "INSERT INTO users (id, tenant_id, email, role_level, password_hash, is_admin) "
                "VALUES (gen_random_uuid(), %s, %s, 1, %s, TRUE)",
                (tenant, f"admin@{tenant}.test", password_hash),
            )
    print(f"Demo users created (password for all: {DEMO_PASSWORD})")
    for key, (_, tenant, level) in users.items():
        print(f"  {key}@{tenant}.test   level {level}")


if __name__ == "__main__":
    main()
