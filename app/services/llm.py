"""Thin client for the model server. Agents build their own prompts and call chat()."""
import httpx

from app import config


class LLMUnavailable(RuntimeError):
    """The model server could not be reached or returned an error."""


async def chat(system: str, user: str, *, model: str | None = None, num_ctx: int | None = None,
               num_predict: int | None = None, timeout: float = 180.0) -> str:
    if config.LLM_PROVIDER != "ollama":
        raise LLMUnavailable(f"Unsupported LLM_PROVIDER: {config.LLM_PROVIDER}")
    # Every agent must use the same context size: Ollama reloads the model whenever it changes.
    options = {"temperature": 0, "num_ctx": num_ctx or config.LLM_NUM_CTX}
    if num_predict:
        options["num_predict"] = num_predict
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{config.OLLAMA_URL}/api/chat",
                json={
                    "model": model or config.LLM_MODEL,
                    "stream": False,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "options": options,
                },
            )
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"Could not reach the model server: {exc.__class__.__name__}") from exc
    if response.status_code != 200:
        raise LLMUnavailable(f"Model server returned status {response.status_code}")
    return response.json().get("message", {}).get("content", "").strip()
