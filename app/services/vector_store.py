from typing import Any, Dict, List
import psycopg
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb
from app.config import DATABASE_URL, EMBEDDING_DIM
from app.services.embedder import embed_texts

class VectorStoreService:
    def _connect(self) -> psycopg.Connection:
        conn = psycopg.connect(DATABASE_URL)
        register_vector(conn)
        return conn

    def init_schema(self) -> None:
        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

            # 1. Users Table (RBAC Levels)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    email TEXT NOT NULL,
                    role_level INT NOT NULL, -- 1: Analyst, 2: Manager, 3: Director, 4: Partner
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )

            # 2. Engagements Table (Client Projects / Secure Workspaces)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS engagements (
                    id UUID PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )

            # 3. Engagement Members Junction Table (Need-to-Know Access)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS engagement_members (
                    engagement_id UUID REFERENCES engagements(id) ON DELETE CASCADE,
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    PRIMARY KEY (engagement_id, user_id)
                )
                """
            )

            # 4. Parent Chunks Table (Classification Level & Optional Engagement ID)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS parent_chunks (
                    id UUID PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    document_id UUID NOT NULL,
                    content TEXT NOT NULL,
                    classification_level INT NOT NULL DEFAULT 1,
                    engagement_id UUID REFERENCES engagements(id) ON DELETE SET NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_parents_tenant ON parent_chunks (tenant_id)")

            # 5. Child Chunks Table (Vector + BM25 FTS)
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS child_chunks (
                    id BIGSERIAL PRIMARY KEY,
                    parent_id UUID NOT NULL REFERENCES parent_chunks(id) ON DELETE CASCADE,
                    tenant_id TEXT NOT NULL,
                    document_id UUID NOT NULL,
                    chunk_index INT NOT NULL,
                    content TEXT NOT NULL,
                    fts_content tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
                    embedding vector({EMBEDDING_DIM}) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_children_tenant ON child_chunks (tenant_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_children_fts ON child_chunks USING gin (fts_content)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_children_embedding "
                "ON child_chunks USING hnsw (embedding vector_cosine_ops)"
            )

    def add_parent_and_children(
        self,
        parent_id: str,
        tenant_id: str,
        document_id: str,
        parent_content: str,
        child_chunks: List[str],
        classification_level: int,
        engagement_id: str | None,
        metadata: Dict[str, Any],
    ) -> None:
        embeddings = embed_texts(child_chunks)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO parent_chunks (id, tenant_id, document_id, content, classification_level, engagement_id, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (parent_id, tenant_id, document_id, parent_content, classification_level, engagement_id, Jsonb(metadata)),
                )
                child_rows = [
                    (parent_id, tenant_id, document_id, i, child, embeddings[i])
                    for i, child in enumerate(child_chunks)
                ]
                cur.executemany(
                    """
                    INSERT INTO child_chunks (parent_id, tenant_id, document_id, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    child_rows,
                )

    def secure_hybrid_rrf_search(
        self, tenant_id: str, user_id: str, user_level: int, query: str, top_k: int = 5, k_rrf: int = 60
    ) -> List[Dict[str, Any]]:
        query_embedding = embed_texts([query])[0]
        sql_secure_rrf = """
        WITH allowed_parents AS (
            SELECT id FROM parent_chunks
            WHERE tenant_id = %s
              AND classification_level <= %s
              AND (
                  engagement_id IS NULL
                  OR engagement_id IN (
                      SELECT engagement_id FROM engagement_members WHERE user_id = %s
                  )
              )
        ),
        vector_search AS (
            SELECT c.parent_id, c.id AS child_id, c.content,
                   ROW_NUMBER() OVER (ORDER BY c.embedding <=> %s) AS rank
            FROM child_chunks c
            JOIN allowed_parents a ON c.parent_id = a.id
            WHERE c.tenant_id = %s
            ORDER BY c.embedding <=> %s
            LIMIT 20
        ),
        text_search AS (
            SELECT c.parent_id, c.id AS child_id, c.content,
                   ROW_NUMBER() OVER (ORDER BY ts_rank(c.fts_content, plainto_tsquery('english', %s)) DESC) AS rank
            FROM child_chunks c
            JOIN allowed_parents a ON c.parent_id = a.id
            WHERE c.tenant_id = %s AND c.fts_content @@ plainto_tsquery('english', %s)
            ORDER BY rank
            LIMIT 20
        ),
        fused_scores AS (
            SELECT COALESCE(v.parent_id, t.parent_id) AS parent_id,
                   COALESCE(1.0 / (%s + v.rank), 0.0) + COALESCE(1.0 / (%s + t.rank), 0.0) AS rrf_score
            FROM vector_search v
            FULL OUTER JOIN text_search t ON v.child_id = t.child_id
        )
        SELECT p.id, p.document_id, p.content AS parent_content, p.metadata,
               MAX(f.rrf_score) AS score
        FROM fused_scores f
        JOIN parent_chunks p ON f.parent_id = p.id
        GROUP BY p.id, p.document_id, p.content, p.metadata
        ORDER BY score DESC
        LIMIT %s;
        """

        with self._connect() as conn:
            rows = conn.execute(
                sql_secure_rrf,
                (
                    tenant_id, user_level, user_id,
                    query_embedding, tenant_id, query_embedding,
                    query, tenant_id, query,
                    k_rrf, k_rrf,
                    top_k
                ),
            ).fetchall()

        return [
            {
                "parent_id": str(r[0]),
                "document_id": str(r[1]),
                "parent_content": r[2],
                "metadata": r[3],
                "rrf_score": float(r[4]),
            }
            for r in rows
        ]
