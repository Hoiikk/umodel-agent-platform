"""Ask Go for a plan or for graph rows, then execute storage plans locally.

.entity_set without an entity-call is a business read. Open-source UModel rejects
that SPL, and this module follows the model pack's links to MySQL or HTTP.
get_metrics / get_logs keep the plan Go already rendered.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from .audit_logger import log_access
from .auth_context import Principal
from .client import UModelClient
from .config import Settings, load_settings
from .data_masker import mask_rows
from .errors import AssistantError
from .executors.base import FetchPlan
from .executors.clickhouse_executor import ClickHouseExecutor
from .executors.es_executor import EsExecutor
from .executors.http_executor import HttpExecutor
from .executors.mysql_executor import MysqlExecutor, Runner
from .executors.promql_executor import PromQLExecutor
from .model_pack import ModelPack
from .plan_normalize import normalize
from .plan_validate import route_plan
from .policy import Policy
from .renderers import PlanRenderer
from .secret_resolver import SecretResolver
from .security_guard import SecurityGuard, sanitize_log_text

_LOCAL_PLAN_ERROR = "requires entity-call"


class Assistant:
    def __init__(
        self,
        settings: Settings | None = None,
        go: UModelClient | None = None,
        mysql_runner: Runner | None = None,
        http_client: Any = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.go = go or UModelClient(self.settings)
        self.guard = SecurityGuard()
        self.secrets = SecretResolver(self.settings.secret_provider)
        self.pack = ModelPack(self.settings.model_root)
        self.renderer = PlanRenderer(self.pack, self.guard, self.settings)
        self.policy = Policy(self.pack.entity_names(), self.pack.event_fields())
        allowed = self.settings.allowed_hosts
        self.mysql = MysqlExecutor(self.guard, self.secrets, mysql_runner)
        self.http = HttpExecutor(self.guard, allowed, self.secrets, http_client)
        self.promql = PromQLExecutor(self.guard, allowed, http_client)
        self.es = EsExecutor(self.guard, allowed, http_client)
        self.clickhouse = ClickHouseExecutor(self.guard, allowed, http_client)

    def execute_sync(self, spl: str, mode: str, principal: Principal) -> dict[str, Any]:
        async def run() -> dict[str, Any]:
            try:
                return await self.execute(spl, mode, principal)
            finally:
                await self.mysql.close()

        return asyncio.run(run())

    async def execute(self, spl: str, mode: str, principal: Principal) -> dict[str, Any]:
        started = time.perf_counter()
        route = "go"
        statement = ""
        try:
            mode_norm = (mode or "data").strip().lower()
            if mode_norm not in {"plan", "data"}:
                raise AssistantError("bad_mode", "mode must be plan or data")
            if not principal or not principal.user_id:
                raise AssistantError("unauthenticated", "a caller identity is required")
            raw = self.go.execute(spl)
            norm = normalize(raw)
            if norm.kind == "error" and text_is_local_entity_read(spl, norm.message):
                plan = self.renderer.render_spl(spl, principal)
                route = plan.route
                statement = plan.sql or plan.url
                result = await self._finish_local(plan, mode_norm, principal)
            elif norm.kind == "error":
                raise AssistantError(norm.code or "go_error", norm.message, norm.details)
            elif norm.kind == "rows":
                self.policy.allow_graph(principal)
                route = "graph"
                result = {"ok": True, "route": "graph", "mode": mode_norm, "data": norm.rows}
            else:
                plan = self._from_go(norm.plan or {}, principal)
                route = plan.route
                statement = plan.sql or plan.url or str((plan.raw_plan.get("query") or {}).get("dialect") or "")
                result = await self._finish_local(plan, mode_norm, principal)
            self._audit(principal, spl, route, statement, result, started, "ok")
            return result
        except AssistantError as exc:
            self._audit(principal, spl, route, statement, {}, started, exc.code)
            return exc.as_dict()

    def explain(self, spl: str) -> dict[str, Any]:
        try:
            return {"ok": True, "explain": self.go.explain(spl)}
        except AssistantError as exc:
            return exc.as_dict()

    async def _finish_local(self, plan: FetchPlan, mode: str, principal: Principal) -> dict[str, Any]:
        if plan.entity_set:
            self.policy.allow_entity(principal, plan.entity_set)
        body: dict[str, Any] = {"ok": True, "route": plan.route, "mode": mode, "plan": plan.public()}
        if mode == "plan":
            return body
        rows = await self._run(plan)
        rows = rename_rows(rows, plan.name_map)
        rows = self.policy.project(rows, plan.allowed_fields)
        rows = mask_rows(rows, plan.field_tags)
        body["data"] = rows
        return body

    async def _run(self, plan: FetchPlan) -> list[dict[str, Any]]:
        try:
            if plan.route == "mysql":
                return await self.mysql.execute(plan)
            if plan.route == "http":
                return await self.http.execute(plan)
            if plan.route == "promql":
                return await self.promql.execute(plan)
            if plan.route == "es":
                return await self.es.execute(plan)
            if plan.route == "clickhouse":
                return await self.clickhouse.execute(plan)
        except AssistantError:
            raise
        except Exception as exc:
            raise AssistantError("storage_error", sanitize_log_text(f"{plan.route} request failed: {exc}")) from exc
        raise AssistantError("unknown_dialect", plan.route)

    def _from_go(self, raw: dict[str, Any], principal: Principal) -> FetchPlan:
        route = route_plan(raw)
        if route in {"mysql", "http"}:
            # Go did not render executable SQL/HTTP for these kinds. Rebuild from the model.
            source = str(raw.get("source_query") or "")
            if source.startswith(".entity_set"):
                return self.renderer.render_spl(source, principal)
            raise AssistantError("not_runnable", "mysql/http plan is missing the source entity_set query")
        return FetchPlan(route=route, raw_plan=raw)

    def _audit(
        self,
        principal: Principal,
        spl: str,
        route: str,
        statement: str,
        result: dict[str, Any],
        started: float,
        status: str,
    ) -> None:
        rows = result.get("data")
        log_access(
            {
                "user_id": getattr(principal, "user_id", ""),
                "tenant_id": getattr(principal, "tenant_id", ""),
                "spl": spl,
                "route": route,
                "statement": statement,
                "row_count": len(rows) if isinstance(rows, list) else 0,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "status": status,
            },
            enabled=self.settings.audit,
        )


def rename_rows(rows: list[dict[str, Any]], name_map: dict[str, str]) -> list[dict[str, Any]]:
    if not name_map:
        return rows
    renamed: list[dict[str, Any]] = []
    for row in rows:
        copy = dict(row)
        for field, source in name_map.items():
            if source != field and source in copy and field not in copy:
                copy[field] = copy.pop(source)
        renamed.append(copy)
    return renamed


def text_is_local_entity_read(spl: str, message: str) -> bool:
    """Recognize the open-source server's stable refusal across error-code variants."""
    return spl.strip().startswith(".entity_set") and _LOCAL_PLAN_ERROR in message


def example_queries() -> list[str]:
    return [
        ".umodel with(kind='entity_set') | project domain,name | sort domain,name | limit 20",
        ".entity with(domain='commerce', name='commerce.user') | limit 20",
        ".topo | limit 20",
        ".entity_set with(domain='commerce', name='commerce.user', ids=['U-1001'])",
        ".entity_set with(domain='commerce', name='commerce.order', ids=['U-1001'])",
        ".entity_set with(domain='commerce', name='commerce.payment', ids=['P-3001'])",
    ]
