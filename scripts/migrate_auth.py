import psycopg

from app.config import DATABASE_URL

STATEMENTS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
    "DELETE FROM users a USING users b WHERE a.ctid < b.ctid AND lower(a.email) = lower(b.email)",
    "CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_idx ON users (lower(email))",
]

if __name__ == "__main__":
    with psycopg.connect(DATABASE_URL) as conn:
        for statement in STATEMENTS:
            conn.execute(statement)
    print("Auth columns ready")
