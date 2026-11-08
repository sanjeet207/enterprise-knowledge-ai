"""Thin client for the model server. Agents build their own prompts and call chat()."""
import asyncio

import httpx

from app import config, tracing


RETRY_PAUSE = 1.0


class LLMUnavailable(RuntimeError):
    """The model server could not be reached or returned an error."""


async def chat(system: str, user: str, *, model: str | None = None, num_ctx: int | None = None,
               num_predict: int | None = None, timeout: float = 180.0, schema: dict | None = None) -> str:
    if config.LLM_PROVIDER != "ollama":
        raise LLMUnavailable(f"Unsupported LLM_PROVIDER: {config.LLM_PROVIDER}")
    # Every agent must use the same context size: Ollama reloads the model whenever it changes.
    options = {"temperature": 0, "num_ctx": num_ctx or config.LLM_NUM_CTX}
    if num_predict:
        options["num_predict"] = num_predict
    payload = {
        "model": model or config.LLM_MODEL,
        "stream": False,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "options": options,
    }
    if schema:
        payload["format"] = schema  # the server constrains the reply to this JSON shape
    with tracing.span("llm.chat", **{"llm.model": payload["model"], "llm.structured": bool(schema)}) as sp:
        # The local model server sometimes drops a request while it unloads or reloads the model (seen twice in 86
        # evaluation questions). One quick retry on a refused connection or a 5xx answer hides that; a timeout is
        # not retried, because the model was working and a second wait would only double the delay.
        for attempt in (1, 2):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(f"{config.OLLAMA_URL}/api/chat", json=payload)
            except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                if attempt == 1:
                    await asyncio.sleep(RETRY_PAUSE)
                    continue
                raise LLMUnavailable(f"Could not reach the model server: {exc.__class__.__name__}") from exc
            except httpx.HTTPError as exc:
                raise LLMUnavailable(f"Could not reach the model server: {exc.__class__.__name__}") from exc
            if response.status_code >= 500 and attempt == 1:
                await asyncio.sleep(RETRY_PAUSE)
                continue
            break
        sp.set(**{"http.status": response.status_code})
        if response.status_code != 200:
            raise LLMUnavailable(f"Model server returned status {response.status_code}")
        return response.json().get("message", {}).get("content", "").strip()
