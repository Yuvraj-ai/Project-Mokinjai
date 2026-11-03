from typing import Any
import json

import httpx
from app.engine.modules.base import BaseModule
from app.engine.context import ExecutionContext


class HttpRequestModule(BaseModule):
    """HTTP request module - makes external API calls."""

    module_type = "http_request"

    async def execute(
        self,
        config: dict[str, Any],
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        method = config.get("method", "GET").upper()
        url = config.get("url", "")
        body = config.get("body", None)
        timeout = config.get("timeout", 30)

        # The properties panel stores headers as a JSON string in a textarea; a
        # dict arrives from saved workflows written before that editor existed.
        headers = config.get("headers", {})
        if isinstance(headers, str):
            try:
                headers = json.loads(headers) if headers.strip() else {}
            except json.JSONDecodeError:
                headers = {}
        if not isinstance(headers, dict):
            headers = {}

        # Substitute input variables in URL
        input_value = inputs.get("input", "")
        if isinstance(input_value, str) and "{{input}}" in url:
            url = url.replace("{{input}}", input_value)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=body if method in ("POST", "PUT", "PATCH") else None,
            )

        try:
            response_data = response.json()
        except Exception:
            response_data = response.text

        return {
            "output": response_data,
            "status_code": response.status_code,
            "headers": dict(response.headers),
        }
