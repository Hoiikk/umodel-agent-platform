"""Run an elasticsearch_dsl plan against the endpoint carried in the plan."""

from __future__ import annotations

from typing import Any

import httpx

from ..errors import AssistantError
from ..plan_validate import require_endpoint
from ..security_guard import SecurityGuard
from .base import FetchPlan


class EsExecutor:
    def __init__(
        self, guard: SecurityGuard, allowed_hosts: frozenset[str], client: httpx.AsyncClient | None = None
    ) -> None:
        self._guard = guard
        self._allowed = allowed_hosts
        self._client = client

    async def execute(self, plan: FetchPlan) -> list[dict[str, Any]]:
        raw = plan.raw_plan
        query = raw.get("query") if isinstance(raw.get("query"), dict) else {}
        index = str(query.get("index") or "")
        body = query.get("body")
        if not index or not isinstance(body, dict):
            raise AssistantError("not_runnable", "elasticsearch plan needs query.index and query.body")
        endpoint = require_endpoint(raw).rstrip("/")
        url = self._guard.validate_http_url(f"{endpoint}/{index}/_search", self._allowed)
        if self._client is not None:
            response = await self._client.post(url, json=body)
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=body)
        response.raise_for_status()
        payload = response.json()
        hits = payload.get("hits", {}).get("hits") if isinstance(payload, dict) else None
        if isinstance(hits, list):
            return [hit.get("_source", hit) if isinstance(hit, dict) else {"value": hit} for hit in hits]
        return [{"data": payload}]
