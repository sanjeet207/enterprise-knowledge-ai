from typing import List


class TextChunker:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks by words."""
        words = text.split()
        if not words:
            return []

        chunks = []
        step = self.chunk_size - self.chunk_overlap
        for i in range(0, len(words), step):
            chunks.append(" ".join(words[i:i + self.chunk_size]))
            if i + self.chunk_size >= len(words):
                break
        return chunks
