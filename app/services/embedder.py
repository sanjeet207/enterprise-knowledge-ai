"""Text embeddings. Two providers, chosen by EMBEDDING_PROVIDER:

  local   sentence-transformers inside the app (default; all-MiniLM-L6-v2, 384 numbers per text)
  ollama  a model served by Ollama, e.g. nomic-embed-text (768) or bge-m3 (1024); no API key

The number of values per text (EMBEDDING_DIM) must match the database column. After changing provider, model or
dimension run `python -m scripts.reindex_embeddings`, which re-embeds the stored chunks (no re-upload needed).
"""
from functools import lru_cache
from typing import List

import numpy as np

from app import config

BATCH = 32
# Models that were trained with a task prefix must be given it, or retrieval quality drops.
PREFIXES = {
    "nomic-embed-text": ("search_document: ", "search_query: "),
}


def prefix_for(model: str, kind: str) -> str:
    """Prefix for a 'document' or a 'query' text; empty for models that need none."""
    pair = PREFIXES.get(model.split(":")[0].strip().lower())
    if not pair:
        return ""
    return pair[0] if kind == "document" else pair[1]


def normalize(vectors) -> np.ndarray:
    """Unit length rows, so cosine distance in the database behaves the same for every model."""
    arr = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(config.EMBEDDING_MODEL)


def _ollama_embed(texts: List[str]) -> list:
    import httpx
    out: list = []
    for i in range(0, len(texts), BATCH):
        try:
            r = httpx.post(f"{config.OLLAMA_URL}/api/embed",
                           json={"model": config.EMBEDDING_MODEL, "input": texts[i:i + BATCH]}, timeout=120.0)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Could not reach Ollama for embeddings: {exc.__class__.__name__}") from exc
        if r.status_code != 200:
            raise RuntimeError(f"Ollama embeddings returned status {r.status_code} "
                               f"(is the model pulled? ollama pull {config.EMBEDDING_MODEL})")
        out.extend(r.json().get("embeddings", []))
    if len(out) != len(texts):
        raise RuntimeError("Ollama returned the wrong number of embeddings")
    return out


def embed_texts(texts: List[str], kind: str = "document") -> np.ndarray:
    """Embed texts as 'document' (stored chunks) or 'query' (the user's question)."""
    if config.EMBEDDING_PROVIDER == "ollama":
        pre = prefix_for(config.EMBEDDING_MODEL, kind)
        vectors = normalize(_ollama_embed([pre + t for t in texts]))
    else:
        vectors = _get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    if vectors.shape[1] != config.EMBEDDING_DIM:
        raise RuntimeError(f"Embedding size {vectors.shape[1]} does not match EMBEDDING_DIM={config.EMBEDDING_DIM}; "
                           "set EMBEDDING_DIM and run python -m scripts.reindex_embeddings")
    return vectors
