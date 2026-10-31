import httpx
from app.config import DATABASE_URL # or define OLLAMA_HOST

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:7b"

class LLMService:
    @staticmethod
    async def generate_answer(query: str, context_passages: list[str]) -> str:
        context_text = "\n\n".join([f"Source {i+1}:\n{p}" for i, p in enumerate(context_passages)])
        
        prompt = f"""You are an enterprise AI assistant. Answer the user's question accurately using ONLY the provided context passages below. If the answer cannot be found in the context, state that you do not have enough information. Do not fabricate facts.

Context:
{context_text}

User Question: {query}
Answer:"""

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_ctx": 4096
                    }
                }
            )
            if response.status_code != 200:
                raise RuntimeError(f"Ollama generation failed: {response.text}")
            
            return response.json().get("response", "").strip()
