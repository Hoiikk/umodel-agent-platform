"""Run a prometheus_promql plan. The endpoint comes from the Go plan, not from the agent."""

from __future__ import annotations

from typing import Any

import httpx

from ..errors import AssistantError
from ..plan_validate import require_endpoint
from ..security_guard import SecurityGuard
from .base import FetchPlan


class PromQLExecutor:
    def __init__(
        self, guard: SecurityGuard, allowed_hosts: frozenset[str], client: httpx.AsyncClient | None = None
    ) -> None:
        self._guard = guard
        self._allowed = allowed_hosts
        self._client = client

    async def execute(self, plan: FetchPlan) -> list[dict[str, Any]]:
        raw = plan.raw_plan
        query = raw.get("query") if isinstance(raw.get("query"), dict) else {}
        endpoint = require_endpoint(raw).rstrip("/")
        queries = query.get("queries") if isinstance(query.get("queries"), list) else []
        if not queries or not isinstance(queries[0], dict) or not queries[0].get("promql"):
            raise AssistantError("not_runnable", "prometheus plan has no promql")
        prefix = str(query.get("api_prefix") or "/api/v1")
        if not prefix.startswith("/"):
            prefix = "/" + prefix
        query_type = str(query.get("query_type") or "instant")
        path = "/query_range" if query_type == "range" else "/query"
        url = self._guard.validate_http_url(f"{endpoint}{prefix}{path}", self._allowed)
        params: dict[str, Any] = {"query": queries[0]["promql"]}
        if query_type == "range":
            time_range = raw.get("time_range") if isinstance(raw.get("time_range"), dict) else {}
            if not time_range.get("from") or not time_range.get("to") or not query.get("step"):
                raise AssistantError("not_runnable", "range PromQL requires time_range.from, time_range.to, and step")
            params.update({"start": time_range["from"], "end": time_range["to"], "step": query["step"]})
        response = await self._send(url, params)
        response.raise_for_status()
        body = response.json()
        data = body.get("data") if isinstance(body, dict) else None
        result = data.get("result") if isinstance(data, dict) else body
        if isinstance(result, list):
            return [row if isinstance(row, dict) else {"value": row} for row in result]
        return [{"data": body}]

    async def _send(self, url: str, params: dict[str, Any]) -> httpx.Response:
        if self._client is not None:
            return await self._client.get(url, params=params)
        async with httpx.AsyncClient(timeout=10.0) as client:
            return await client.get(url, params=params)
