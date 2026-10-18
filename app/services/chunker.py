from typing import List, Dict, Any

class HierarchicalChunker:
    def __init__(self, parent_size: int = 200, child_size: int = 50):
        self.parent_size = parent_size
        self.child_size = child_size

    def chunk_document(self, text: str) -> List[Dict[str, Any]]:
        words = text.split()
        if not words:
            return []
        
        chunks = []
        for i in range(0, len(words), self.parent_size):
            parent_words = words[i:i + self.parent_size]
            parent_content = " ".join(parent_words)
            
            child_chunks = [
                " ".join(parent_words[j:j + self.child_size])
                for j in range(0, len(parent_words), self.child_size)
            ]
            chunks.append({
                "parent_content": parent_content,
                "child_chunks": child_chunks
            })
        return chunks
