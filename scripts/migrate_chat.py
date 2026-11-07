import psycopg

from app.config import DATABASE_URL

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id UUID PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS conversations_user_idx ON conversations (user_id, updated_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id BIGSERIAL PRIMARY KEY,
        conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        question TEXT,
        outcome TEXT,
        sources JSONB NOT NULL DEFAULT '[]'::jsonb,
        rating INT,
        feedback_comment TEXT,
        rated_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS chat_messages_conv_idx ON chat_messages (conversation_id, id)",
    """
    CREATE TABLE IF NOT EXISTS research_reports (
        id UUID PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        request TEXT NOT NULL,
        report JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        reviewed_at TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS research_reports_user_idx ON research_reports (user_id, created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS ingest_jobs (
        id UUID PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        user_id UUID NOT NULL,
        document_id UUID NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL DEFAULT '',
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        status TEXT NOT NULL DEFAULT 'queued',
        attempts INT NOT NULL DEFAULT 0,
        error TEXT,
        error_status INT,
        result JSONB,
        run_after TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        started_at TIMESTAMPTZ,
        finished_at TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS ingest_jobs_queue_idx ON ingest_jobs (status, run_after, created_at)",
    "CREATE INDEX IF NOT EXISTS ingest_jobs_user_idx ON ingest_jobs (tenant_id, user_id, created_at DESC)",
]

if __name__ == "__main__":
    with psycopg.connect(DATABASE_URL) as conn:
        for statement in STATEMENTS:
            conn.execute(statement)
    print("Conversation tables ready")
