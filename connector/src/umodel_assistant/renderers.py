"""Build a parameterized MySQL or HTTP fetch from the model pack."""

from __future__ import annotations

import os
import re
from typing import Any

from .auth_context import Principal
from .config import Settings
from .errors import AssistantError
from .executors.base import FetchPlan
from .model_pack import ModelPack
from .security_guard import SecurityGuard

_DOMAIN = re.compile(r"domain\s*=\s*'([^']*)'", re.IGNORECASE)
_NAME = re.compile(r"name\s*=\s*'([^']*)'", re.IGNORECASE)
_IDS = re.compile(r"ids\s*=\s*\[([^\]]*)\]", re.IGNORECASE)
_ID = re.compile(r"'([^']*)'")
_FILTER = re.compile(r"(?:^|[\s,])(status|position)\s*=\s*'([^']*)'", re.IGNORECASE)
_POSITION_VALUE = re.compile("^[\u4e00-\u9fffA-Za-z0-9]{1,32}$")
_STATUSES = frozenset({"APPLIED", "SCREENING", "INTERVIEWING", "HIRED", "REJECTED"})
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


class PlanRenderer:
    def __init__(self, pack: ModelPack, guard: SecurityGuard, settings: Settings) -> None:
        self.pack = pack
        self.guard = guard
        self.settings = settings

    def render_spl(self, spl: str, principal: Principal) -> FetchPlan:
        text = (spl or "").strip()
        if not text.startswith(".entity_set"):
            raise AssistantError("local_render", "local rendering only applies to .entity_set reads")
        domain = _first(_DOMAIN, text, "domain")
        name = _first(_NAME, text, "name")
        found = _IDS.search(text)
        ids = _ID.findall(found.group(1)) if found else []
        filters = _FILTER.findall(text)
        if ids and filters:
            raise AssistantError("spl", "entity_set accepts ids or one field filter, not both")
        if ids:
            return self.render_entity(domain, name, ids[0], principal)
        if len(filters) == 1:
            column, value = filters[0]
            self._check_filter(column.lower(), value)
            return self.render_entity(domain, name, value, principal, lookup=column.lower())
        if filters:
            raise AssistantError("spl", "entity_set accepts one field filter")
        raise AssistantError("missing_ids", "entity_set live fetch needs ids=['...']")

    def render_entity(
        self, domain: str, name: str, entity_id: str, principal: Principal, lookup: str | None = None
    ) -> FetchPlan:
        bound = self.pack.binding(domain, name)
        storage = bound["storage"]
        kind = str(storage.get("kind") or "")
        if lookup is not None and kind != "mysql":
            raise AssistantError("local_render", "field filters are only rendered for mysql entity sets")
        if kind == "mysql":
            plan = self._mysql(bound, entity_id, principal, lookup=lookup)
        elif kind == "external_storage":
            plan = self._http(bound, entity_id, principal)
        else:
            raise AssistantError("unknown_dialect", f"no local renderer for storage kind {kind}")
        plan.entity_set = name
        plan.event_set = str(bound["event"].get("metadata", {}).get("name") or "")
        plan.allowed_fields = self.pack.event_fields().get(plan.event_set)
        plan.field_tags = self.pack.field_tags(plan.event_set)
        mapping = bound["storage_link"]["spec"].get("fields_mapping") or {}
        plan.name_map = {str(field): str(column) for field, column in mapping.items()}
        return plan

    def _check_filter(self, column: str, value: str) -> None:
        if column == "status" and value in _STATUSES:
            return
        if column == "position" and _POSITION_VALUE.fullmatch(value):
            return
        raise AssistantError("spl", "filter must be one candidate status or one position")

    def _mysql(
        self, bound: dict[str, Any], entity_id: str, principal: Principal, lookup: str | None = None
    ) -> FetchPlan:
        spec = bound["storage"]["spec"]
        mapping = bound["storage_link"]["spec"].get("fields_mapping") or {}
        columns: list[str] = []
        seen: set[str] = set()
        for column in mapping.values():
            text = str(column)
            if text not in seen:
                seen.add(text)
                columns.append(self.guard.quote_ident(text))
        if not columns:
            raise AssistantError("model_link", "storage_link fields_mapping is empty")
        if lookup is None:
            lookup = str(spec.get("lookup_field") or "")
            if not lookup:
                primary = (bound["entity"].get("spec") or {}).get("primary_key_fields") or []
                if not primary:
                    raise AssistantError("model_link", "storage has no lookup_field and the entity set has no primary key")
                lookup = str(mapping.get(primary[0]) or primary[0])
            uid = self.guard.require_safe_id(entity_id)
        elif lookup not in {str(column) for column in mapping.values()}:
            raise AssistantError("model_link", f"storage does not map filter field {lookup}")
        else:
            uid = entity_id
        params: list[Any] = [uid]
        where = f"{self.guard.quote_ident(lookup)} = %s"
        tenant_field = spec.get("tenant_field")
        if tenant_field:
            if not principal.tenant_id:
                raise AssistantError("tenant_required", "storage declares tenant_field but the caller has no tenant")
            column = str(mapping.get(tenant_field) or tenant_field)
            where += f" AND {self.guard.quote_ident(column)} = %s"
            params.append(principal.tenant_id)
        limit = min(self.settings.max_sql_limit, int(spec.get("default_limit") or self.settings.max_sql_limit))
        database = self.guard.quote_ident(str(spec.get("database") or ""))
        table = self.guard.quote_ident(str(spec.get("table") or ""))
        sql = f"SELECT {', '.join(columns)} FROM {database}.{table} WHERE {where} LIMIT {limit}"
        self.guard.validate_sql(sql)
        endpoint = _runtime_endpoint(spec)
        host, port = _endpoint(endpoint)
        return FetchPlan(
            route="mysql",
            sql=sql,
            params=tuple(params),
            credential_ref=str(spec.get("credential_ref") or ""),
            mysql_target={
                "host": host,
                "port": port,
                "database": spec.get("database"),
                "username": spec.get("username") or "readonly",
            },
        )

    def _http(self, bound: dict[str, Any], entity_id: str, principal: Principal) -> FetchPlan:
        spec = bound["storage"]["spec"]
        properties = spec.get("properties") if isinstance(spec.get("properties"), dict) else {}
        endpoint = str(properties.get("endpoint") or "").rstrip("/")
        template = str(properties.get("path_template") or "")
        names = _PLACEHOLDER.findall(template)
        if len(names) != 1:
            raise AssistantError("model_link", "HTTP path_template must contain one {field} placeholder")
        uid = self.guard.require_safe_id(entity_id)
        path = template.replace("{" + names[0] + "}", uid)
        if "{" in path:
            raise AssistantError("model_link", "HTTP path_template was not fully rendered")
        if not path.startswith("/"):
            path = "/" + path
        url = self.guard.validate_http_url(f"{endpoint}{path}", self.settings.allowed_hosts)
        headers: dict[str, str] = {}
        header_name = str(spec.get("tenant_header") or "")
        if header_name and principal.tenant_id:
            headers[header_name] = principal.tenant_id
        pagination = spec.get("pagination") if isinstance(spec.get("pagination"), dict) else None
        return FetchPlan(
            route="http",
            url=url,
            method="GET",
            headers=headers,
            credential_ref=str(spec.get("credential_ref") or properties.get("credential_ref") or ""),
            pagination=pagination,
        )


def _first(pattern: re.Pattern[str], text: str, label: str) -> str:
    found = pattern.search(text)
    if not found or not found.group(1):
        raise AssistantError("spl", f".entity_set is missing {label}")
    return found.group(1)


def _endpoint(endpoint: str) -> tuple[str, int]:
    host, _, port = endpoint.partition(":")
    return host or "127.0.0.1", int(port or "3306")


def _runtime_endpoint(spec: dict[str, Any]) -> str:
    """Use an explicit deployment override without putting secrets in model files."""
    configured = str(spec.get("endpoint") or "127.0.0.1:3306")
    env_name = str(spec.get("endpoint_env") or "").strip()
    return os.environ.get(env_name, configured).strip() if env_name else configured
