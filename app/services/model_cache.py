"""Where the reranker model is stored, and a repair step for a damaged copy.

The model used to live in /tmp, which the operating system clears. A cleared folder can leave an empty
model directory behind, and the reranker library then trusts the directory and fails to open a file that
is not there, so every search crashed. The cache now lives in a permanent folder, and a model directory
without a model file is deleted so that it is downloaded again.
"""
import os
import shutil
from pathlib import Path


def cache_dir() -> str:
    """FLASHRANK_CACHE_DIR if set, otherwise a folder in the user's home that is not cleaned automatically."""
    return os.getenv("FLASHRANK_CACHE_DIR") or str(Path.home() / ".cache" / "enterprise-knowledge-ai" / "flashrank")


def prepare(cache: str, model_name: str) -> str:
    """Make `cache` ready for the reranker: create it, and remove a model folder that has no .onnx file."""
    folder = Path(cache) / model_name
    if folder.exists() and not any(folder.glob("*.onnx")):
        shutil.rmtree(folder, ignore_errors=True)
    Path(cache).mkdir(parents=True, exist_ok=True)
    return cache
