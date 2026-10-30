"""GET against a model-declared URL. Pagination runs only when the storage spec asks for it."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ..errors import AssistantError
from ..secret_resolver import SecretResolver
from ..security_guard import SecurityGuard
from .base import FetchPlan


class HttpExecutor:
    def __init__(
        self,
        guard: SecurityGuard,
        allowed_hosts: frozenset[str],
        secrets: SecretResolver,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._guard = guard
        self._allowed = allowed_hosts
        self._secrets = secrets
        self._client = client

    async def execute(self, plan: FetchPlan) -> list[dict[str, Any]]:
        if plan.method.upper() != "GET":
            raise AssistantError("http_method", f"business HTTP reads are GET, got {plan.method}")
        rows: list[dict[str, Any]] = []
        url: str | None = self._guard.validate_http_url(plan.url, self._allowed)
        pages = 0
        max_pages = int((plan.pagination or {}).get("max_pages") or 1)
        next_field = str((plan.pagination or {}).get("next_field") or "")
        while url and pages < max_pages:
            pages += 1
            payload = await self._get(url, plan)
            if isinstance(payload, list):
                rows.extend(row for row in payload if isinstance(row, dict))
                url = None
            elif isinstance(payload, dict):
                rows.append(payload)
                nxt = payload.get(next_field) if next_field else None
                url = self._guard.validate_http_url(str(nxt), self._allowed) if isinstance(nxt, str) and nxt else None
            else:
                raise AssistantError("http_payload", f"unexpected REST payload type: {type(payload).__name__}")
            if not plan.pagination:
                break
        return rows

    async def _get(self, url: str, plan: FetchPlan) -> Any:
        headers = dict(plan.headers)
        if plan.credential_ref:
            headers["Authorization"] = f"Bearer {self._secrets.resolve(plan.credential_ref)}"
        delay = 0.05
        response: httpx.Response | None = None
        for attempt in range(3):
            if self._client is not None:
                response = await self._client.get(url, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, headers=headers)
            if response.status_code not in {502, 503, 504} or attempt == 2:
                break
            await asyncio.sleep(delay)
            delay *= 2
        assert response is not None
        response.raise_for_status()
        return response.json()
