from app.services.vector_store import VectorStoreService

if __name__ == "__main__":
    VectorStoreService().init_schema()
    print("Database schema initialized successfully with pgvector, HNSW, and hybrid search RRF.")
