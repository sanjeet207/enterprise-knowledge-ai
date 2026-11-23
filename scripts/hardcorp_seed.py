"""Load the harder fictional company ("Northwind Capital", tenant "northwind") into the database.

Usage:  python -m scripts.hardcorp_seed            (database needed; embeds about 30 documents, a minute or two)
        python -m scripts.hardcorp_seed --remove   removes the tenant again

Users (password DemoPass2026x, local development only): analyst@northwind.test (level 1), manager@northwind.test (level 2),
director@northwind.test (level 3) and admin@northwind.test (level 1, administrator). Documents are written through the same
chunker and store the application uses, as published, with the level the corpus gives each one.
The tenant is separate from the demo companies, so verify_access and the security matrix are not affected.
"""
import sys
import uuid

from app.security import hash_password
from app.services.chunker import HierarchicalChunker
from app.services.vector_store import VectorStoreService
from scripts import hardcorp_data as h

PASSWORD = "DemoPass2026x"  # local development only


def remove(store: VectorStoreService) -> None:
    with store._connect() as conn:
        conn.execute("DELETE FROM parent_chunks WHERE tenant_id = %s", (h.TENANT,))
        conn.execute("DELETE FROM users WHERE tenant_id = %s", (h.TENANT,))


def seed(store: VectorStoreService) -> int:
    remove(store)
    password_hash = hash_password(PASSWORD)
    with store._connect() as conn:
        for name, level in h.USERS.items():
            conn.execute("INSERT INTO users (id, tenant_id, email, role_level, password_hash) VALUES (%s, %s, %s, %s, %s)",
                         (str(uuid.uuid4()), h.TENANT, f"{name}@{h.TENANT}.test", level, password_hash))
        conn.execute("INSERT INTO users (id, tenant_id, email, role_level, password_hash, is_admin) VALUES (%s, %s, %s, 1, %s, TRUE)",
                     (str(uuid.uuid4()), h.TENANT, f"admin@{h.TENANT}.test", password_hash))
    chunker = HierarchicalChunker()
    chunks = 0
    for doc in h.build_documents():
        document_id = str(uuid.uuid4())
        for item in chunker.chunk_document(doc["text"]):
            store.add_parent_and_children(parent_id=str(uuid.uuid4()), tenant_id=h.TENANT, document_id=document_id,
                                          parent_content=item["parent_content"], child_chunks=item["child_chunks"],
                                          classification_level=doc["level"], engagement_id=None,
                                          metadata={"title": doc["title"]})
            chunks += len(item["child_chunks"])
    return chunks


def main() -> None:
    store = VectorStoreService()
    if "--remove" in sys.argv:
        remove(store)
        print("Northwind removed.")
        return
    chunks = seed(store)
    print(f"Northwind Capital loaded: {len(h.build_documents())} documents, {chunks} passages. "
          f"Users analyst/manager/director/admin@{h.TENANT}.test, password {PASSWORD}")


if __name__ == "__main__":
    main()
