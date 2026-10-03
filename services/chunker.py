from typing import List

class TextChunker:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks by words."""
        words = text.split()
        if not words:
            return []

        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i:i + self.chunk_size])
            chunks.append(chunk)
            i += self.chunk_size - self.chunk_overlap

        return chunks
