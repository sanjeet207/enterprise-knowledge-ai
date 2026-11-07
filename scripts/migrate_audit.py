import psycopg

from app.config import DATABASE_URL

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id BIGSERIAL PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        tenant_id TEXT NOT NULL,
        user_id UUID NOT NULL,
        user_email TEXT NOT NULL,
        role_level INT NOT NULL,
        query TEXT NOT NULL,
        outcome TEXT NOT NULL,
        top_score DOUBLE PRECISION,
        sources JSONB NOT NULL DEFAULT '[]'::jsonb,
        answer TEXT,
        model TEXT,
        latency_ms INT
    )
    """,
    "ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS rewritten_query TEXT",
    "ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS trace JSONB",
    """
    CREATE TABLE IF NOT EXISTS admin_events (
        id BIGSERIAL PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        tenant_id TEXT NOT NULL,
        actor_id UUID NOT NULL,
        actor_email TEXT NOT NULL,
        action TEXT NOT NULL,
        target TEXT NOT NULL,
        detail JSONB NOT NULL DEFAULT '{}'::jsonb
    )
    """,
    "CREATE INDEX IF NOT EXISTS admin_events_tenant_time_idx ON admin_events (tenant_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS audit_log_tenant_time_idx ON audit_log (tenant_id, created_at DESC)",
]

if __name__ == "__main__":
    with psycopg.connect(DATABASE_URL) as conn:
        for statement in STATEMENTS:
            conn.execute(statement)
    print("Audit table ready")
