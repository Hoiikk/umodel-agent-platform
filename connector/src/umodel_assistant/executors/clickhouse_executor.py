"""Run clickhouse_sql from an official sql-table plan. Kind-only passthrough never reaches here."""

from __future__ import annotations

import re
from typing import Any

import httpx

from ..errors import AssistantError
from ..plan_validate import require_endpoint
from ..security_guard import SecurityGuard
from .base import FetchPlan

_TIME = re.compile(r"^[0-9T:Z.+-]+$")


class ClickHouseExecutor:
    def __init__(
        self, guard: SecurityGuard, allowed_hosts: frozenset[str], client: httpx.AsyncClient | None = None
    ) -> None:
        self._guard = guard
        self._allowed = allowed_hosts
        self._client = client

    async def execute(self, plan: FetchPlan) -> list[dict[str, Any]]:
        raw = plan.raw_plan
        query = raw.get("query") if isinstance(raw.get("query"), dict) else {}
        queries = query.get("queries") if isinstance(query.get("queries"), list) else []
        if not queries or not isinstance(queries[0], dict) or not queries[0].get("sql"):
            raise AssistantError("not_runnable", "clickhouse plan has no sql")
        sql = str(queries[0]["sql"])
        if "{from}" in sql or "{to}" in sql:
            time_range = raw.get("time_range") if isinstance(raw.get("time_range"), dict) else {}
            start, end = str(time_range.get("from") or ""), str(time_range.get("to") or "")
            if not _TIME.fullmatch(start) or not _TIME.fullmatch(end):
                raise AssistantError(
                    "not_runnable", "clickhouse SQL still has {from}/{to}; time_range values must be timestamps"
                )
            sql = sql.replace("{from}", start).replace("{to}", end)
        sql = self._guard.validate_sql(sql)
        endpoint = require_endpoint(raw)
        url = self._guard.validate_http_url(endpoint, self._allowed)
        if self._client is not None:
            response = await self._client.post(url, params={"query": sql})
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, params={"query": sql})
        response.raise_for_status()
        text = response.text
        return [{"raw": line} for line in text.splitlines() if line] or [{"raw": text}]
