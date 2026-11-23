"""Thin client for the language model. Agents build their own prompts and call chat().

One setting, LLM_PROVIDER, picks where the model runs:
  ollama     a local Ollama server (the default; nothing leaves the machine)
  anthropic  the Anthropic API (ANTHROPIC_API_KEY)
  groq       the Groq API (GROQ_API_KEY)
  openai     any OpenAI-compatible endpoint (LLM_API_KEY and LLM_BASE_URL)
Only this file knows about providers; agents, prompts, checks and access control are identical for all of them.
"""
import asyncio
import json
import re

import httpx

from app import config, tracing


RETRY_PAUSE = 1.0
RATE_LIMIT_ATTEMPTS = 4      # a 429 is retried up to three times, waiting as long as the provider asks
RATE_LIMIT_MAX_WAIT = 30.0
REASONING_HEADROOM = 1024   # hosted reasoning models spend max_tokens on hidden thinking before the answer
HOSTED = ("anthropic", "groq", "openai")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLMUnavailable(RuntimeError):
    """The model server could not be reached or returned an error."""


def hosted_model(model: str | None) -> str:
    """Model name to send to a hosted provider. A local tag such as 'qwen2.5:3b' is meaningless there, so it is
    replaced by LLM_MODEL (set LLM_MODEL and any <AGENT>_MODEL / ANSWERER_QUICK_MODEL to hosted names)."""
    if not model or ":" in model:
        return config.LLM_MODEL if ":" not in config.LLM_MODEL else ""
    return model


def api_key(provider: str) -> str:
    key = {"anthropic": config.ANTHROPIC_API_KEY, "groq": config.GROQ_API_KEY, "openai": config.LLM_API_KEY}[provider]
    if not key:
        raise LLMUnavailable(f"LLM_PROVIDER={provider} needs its API key to be set")
    return key


def strip_fences(text: str) -> str:
    """Hosted models sometimes wrap JSON in a code fence; the parsers expect bare JSON."""
    match = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", text, flags=re.S)
    return match.group(1) if match else text


def _retry_after(response) -> float:
    """Seconds the provider asks us to wait after a 429 (Retry-After header), kept between RETRY_PAUSE and 30."""
    try:
        wait = float((getattr(response, "headers", None) or {}).get("retry-after", RETRY_PAUSE))
    except (TypeError, ValueError):
        wait = RETRY_PAUSE
    return min(max(wait, RETRY_PAUSE), RATE_LIMIT_MAX_WAIT) if RETRY_PAUSE else 0


async def _post(url: str, payload: dict, headers: dict | None, timeout: float):
    # The model server sometimes drops a request while it unloads or reloads a model (seen twice in 86 evaluation
    # questions). One quick retry on a refused connection or a 5xx answer hides that; a timeout is not retried,
    # because the model was working and a second wait would only double the delay.
    for attempt in range(1, RATE_LIMIT_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers) if headers else await client.post(url, json=payload)
        except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            if attempt == 1:
                await asyncio.sleep(RETRY_PAUSE)
                continue
            raise LLMUnavailable(f"Could not reach the model server: {exc.__class__.__name__}") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"Could not reach the model server: {exc.__class__.__name__}") from exc
        if response.status_code == 429 and attempt < RATE_LIMIT_ATTEMPTS:
            # A hosted model's per-minute limit: wait as long as the provider says, then try again.
            await asyncio.sleep(_retry_after(response))
            continue
        if response.status_code >= 500 and attempt == 1:
            await asyncio.sleep(RETRY_PAUSE)
            continue
        break
    if response.status_code != 200:
        raise LLMUnavailable(f"Model server returned status {response.status_code}")
    return response


def _with_schema(system: str, schema: dict | None) -> str:
    if not schema:
        return system
    return system + "\n\nReply with only one JSON object that matches this JSON schema, with no other text:\n" + json.dumps(schema)


async def chat(system: str, user: str, *, model: str | None = None, num_ctx: int | None = None,
               num_predict: int | None = None, timeout: float = 180.0, schema: dict | None = None) -> str:
    provider = config.LLM_PROVIDER
    if provider != "ollama" and provider not in HOSTED:
        raise LLMUnavailable(f"Unsupported LLM_PROVIDER: {provider}")
    if provider == "ollama":
        return await _chat_ollama(system, user, model, num_ctx, num_predict, timeout, schema)
    name = hosted_model(model)
    if not name:
        raise LLMUnavailable(f"LLM_PROVIDER={provider} needs LLM_MODEL set to a {provider} model name")
    key = api_key(provider)
    with tracing.span("llm.chat", **{"llm.provider": provider, "llm.model": name, "llm.structured": bool(schema)}) as sp:
        if provider == "anthropic":
            payload = {"model": name, "max_tokens": num_predict or 1024, "temperature": 0,
                       "system": _with_schema(system, schema), "messages": [{"role": "user", "content": user}]}
            headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
            response = await _post(ANTHROPIC_URL, payload, headers, timeout)
            sp.set(**{"http.status": response.status_code})
            text = "".join(b.get("text", "") for b in response.json().get("content", []) if b.get("type") == "text")
        else:
            payload = {"model": name, "temperature": 0,
                       "messages": [{"role": "system", "content": _with_schema(system, schema)},
                                    {"role": "user", "content": user}]}
            if num_predict:
                payload["max_tokens"] = num_predict
            if provider == "groq" and name.startswith("openai/gpt-oss"):
                payload["reasoning_effort"] = "low"
                if num_predict:
                    payload["max_tokens"] = num_predict + REASONING_HEADROOM
            if schema:
                payload["response_format"] = {"type": "json_object"}
            url = GROQ_URL if provider == "groq" else f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions"
            response = await _post(url, payload, {"authorization": f"Bearer {key}"}, timeout)
            sp.set(**{"http.status": response.status_code})
            choices = response.json().get("choices") or [{}]
            text = (choices[0].get("message") or {}).get("content") or ""
        text = text.strip()
        return strip_fences(text).strip() if schema else text


async def _chat_ollama(system, user, model, num_ctx, num_predict, timeout, schema) -> str:
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
        response = await _post(f"{config.OLLAMA_URL}/api/chat", payload, None, timeout)
        sp.set(**{"http.status": response.status_code})
        return response.json().get("message", {}).get("content", "").strip()
