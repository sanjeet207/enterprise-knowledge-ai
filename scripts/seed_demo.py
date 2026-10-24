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
    print(f"Demo users created (password for all: {DEMO_PASSWORD})")
    for key, (_, tenant, level) in users.items():
        print(f"  {key}@{tenant}.test   level {level}")


if __name__ == "__main__":
    main()
