import re
from pathlib import Path

import psycopg

from app.config import DATABASE_URL

PATH = Path("app/services/vector_store.py")

OLD_RULE = re.compile(
    r"AND \(\s*classification_level <= %s\s*OR engagement_id IN \(\s*"
    r"SELECT engagement_id FROM engagement_members WHERE user_id = %s\s*\)\s*\)"
)
NEW_RULE = (
    "AND classification_level <= %s\n"
    "              AND (\n"
    "                  engagement_id IS NULL\n"
    "                  OR engagement_id IN (\n"
    "                      SELECT engagement_id FROM engagement_members WHERE user_id = %s\n"
    "                  )\n"
    "              )"
)


def patch_access_rule() -> None:
    text = PATH.read_text()
    if "engagement_id IS NULL" in text:
        print("Access rule: already fixed.")
        return
    new_text, count = OLD_RULE.subn(lambda match: NEW_RULE, text, count=1)
    if count != 1:
        raise SystemExit(
            "Could not find the old access rule in app/services/vector_store.py. "
            "Paste that file to me and I will patch it by hand."
        )
    PATH.write_text(new_text)
    print("Access rule: fixed (level AND engagement membership).")


def protect_restricted_documents() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("ALTER TABLE parent_chunks DROP CONSTRAINT IF EXISTS parent_chunks_engagement_id_fkey")
        conn.execute(
            "ALTER TABLE parent_chunks ADD CONSTRAINT parent_chunks_engagement_id_fkey "
            "FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE RESTRICT"
        )
    print("Database: deleting an engagement is now blocked while documents belong to it.")


if __name__ == "__main__":
    patch_access_rule()
    protect_restricted_documents()
