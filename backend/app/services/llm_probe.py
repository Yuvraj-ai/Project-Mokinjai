"""One short completion against the configured provider. Failure text is stored as-is."""

import httpx

_TIMEOUT = 120.0


class LlmProbeError(Exception):
    pass


async def probe_llm(
    *,
    provider: str,
    model_id: str,
    api_key: str,
    base_url: str | None,
) -> None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await _send(client, provider, model_id, api_key, base_url)
    except httpx.TimeoutException as exc:
        raise LlmProbeError(f"Request timed out after {_TIMEOUT:.0f}s") from exc
    except httpx.RequestError as exc:
        detail = str(exc).strip().replace("\n", " ") or exc.__class__.__name__
        if len(detail) > 500:
            detail = detail[:500] + "…"
        raise LlmProbeError(f"Connection failed: {detail}") from exc

    if response.status_code >= 400:
        detail = response.text.strip().replace("\n", " ")
        if len(detail) > 500:
            detail = detail[:500] + "…"
        raise LlmProbeError(f"HTTP {response.status_code}: {detail}")


async def _send(
    client: httpx.AsyncClient,
    provider: str,
    model_id: str,
    api_key: str,
    base_url: str | None,
) -> httpx.Response:
    if provider == "anthropic":
        return await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model_id,
                "max_tokens": 16,
                "messages": [{"role": "user", "content": "ping"}],
            },
        )
    if provider == "gemini":
        return await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent",
            headers={"x-goog-api-key": api_key, "content-type": "application/json"},
            json={
                "contents": [{"parts": [{"text": "ping"}]}],
                "generationConfig": {"maxOutputTokens": 16},
            },
        )
    url = _openai_url(base_url)
    return await client.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
        json={
            "model": model_id,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        },
    )


def _openai_url(base_url: str | None) -> str:
    if not base_url:
        return "https://api.openai.com/v1/chat/completions"
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    return f"{trimmed}/chat/completions"
