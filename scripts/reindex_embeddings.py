"""Re-embed every stored chunk with the embedding settings in .env. No documents need to be uploaded again.

Use it after changing EMBEDDING_PROVIDER, EMBEDDING_MODEL or EMBEDDING_DIM. Example for Ollama's nomic-embed-text:
    ollama pull nomic-embed-text
    EMBEDDING_PROVIDER=ollama  EMBEDDING_MODEL=nomic-embed-text  EMBEDDING_DIM=768   (put these in .env)
    python -m scripts.reindex_embeddings
To go back: put the old values in .env and run it again. Stop the server while it runs.
"""
import time

import psycopg
from pgvector.psycopg import register_vector

from app import config
from app.services.embedder import embed_texts

BATCH = 64


def main() -> None:
    print(f"Embedding with provider={config.EMBEDDING_PROVIDER} model={config.EMBEDDING_MODEL} dim={config.EMBEDDING_DIM}")
    started = time.time()
    with psycopg.connect(config.DATABASE_URL, autocommit=True) as conn:
        register_vector(conn)
        total = conn.execute("SELECT count(*) FROM child_chunks").fetchone()[0]
        probe = embed_texts(["test"])  # fails early if the model or size is wrong
        print(f"{total} chunks to embed (model returns {probe.shape[1]} values per text)")
        conn.execute("DROP INDEX IF EXISTS idx_children_embedding")
        conn.execute("ALTER TABLE child_chunks DROP COLUMN IF EXISTS embedding")
        conn.execute(f"ALTER TABLE child_chunks ADD COLUMN embedding vector({config.EMBEDDING_DIM})")
        done, last_id = 0, 0
        while True:
            rows = conn.execute("SELECT id, content FROM child_chunks WHERE id > %s ORDER BY id LIMIT %s",
                                (last_id, BATCH)).fetchall()
            if not rows:
                break
            vectors = embed_texts([r[1] for r in rows])
            with conn.cursor() as cur:
                cur.executemany("UPDATE child_chunks SET embedding = %s WHERE id = %s",
                                [(vectors[i], rows[i][0]) for i in range(len(rows))])
            last_id = rows[-1][0]
            done += len(rows)
            print(f"  {done}/{total}", flush=True)
        conn.execute("ALTER TABLE child_chunks ALTER COLUMN embedding SET NOT NULL")
        conn.execute("CREATE INDEX idx_children_embedding ON child_chunks USING hnsw (embedding vector_cosine_ops)")
    print(f"Done: {done} chunks in {time.time() - started:.0f}s. Start the server and run the evaluations.")


if __name__ == "__main__":
    main()
