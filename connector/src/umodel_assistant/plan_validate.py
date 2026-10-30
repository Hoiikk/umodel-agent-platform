"""Decide which executor can run a Go plan. Passthrough plans fail closed."""

from __future__ import annotations

from typing import Any

from .errors import AssistantError


def route_plan(plan: dict[str, Any]) -> str:
    query = plan.get("query") if isinstance(plan.get("query"), dict) else {}
    dialect = str(query.get("dialect") or "")
    storage = (plan.get("data_source") or {}).get("storage") if isinstance(plan.get("data_source"), dict) else {}
    if not isinstance(storage, dict):
        storage = {}
    kind = str(storage.get("type") or storage.get("kind") or "")
    if dialect == "prometheus_promql":
        return "promql"
    if dialect == "elasticsearch_dsl":
        return "es"
    if dialect == "clickhouse_sql":
        return "clickhouse"
    if kind == "mysql" or dialect == "mysql":
        return "mysql"
    if kind in {"external_storage", "http"} or dialect in {"http", "rest"}:
        return "http"
    if dialect and kind and dialect == kind:
        raise AssistantError(
            "passthrough",
            f"open-source plan for {dialect} has no executable query; set spec.family or include_spec",
            {"dialect": dialect},
        )
    raise AssistantError("unknown_dialect", f"no executor for dialect {dialect or kind!r}")


def require_endpoint(plan: dict[str, Any]) -> str:
    query = plan.get("query") if isinstance(plan.get("query"), dict) else {}
    storage = (plan.get("data_source") or {}).get("storage") if isinstance(plan.get("data_source"), dict) else {}
    config = storage.get("config") if isinstance(storage, dict) and isinstance(storage.get("config"), dict) else {}
    endpoint = str(query.get("endpoint") or config.get("endpoint") or "")
    if not endpoint:
        raise AssistantError(
            "not_runnable",
            "plan is missing storage endpoint; call execute with format=agent and include_spec=true",
        )
    return endpoint
