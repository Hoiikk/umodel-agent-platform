"""A fetch the renderer or a Go plan is allowed to run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FetchPlan:
    route: str
    sql: str = ""
    params: tuple[Any, ...] = ()
    url: str = ""
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    json_body: Any = None
    query_params: dict[str, Any] = field(default_factory=dict)
    raw_plan: dict[str, Any] = field(default_factory=dict)
    entity_set: str = ""
    event_set: str = ""
    allowed_fields: frozenset[str] | None = None
    field_tags: dict[str, str] = field(default_factory=dict)
    credential_ref: str = ""
    name_map: dict[str, str] = field(default_factory=dict)
    mysql_target: dict[str, Any] | None = None
    pagination: dict[str, Any] | None = None

    def public(self) -> dict[str, Any]:
        body: dict[str, Any] = {"route": self.route, "entity_set": self.entity_set}
        if self.sql:
            body["dialect"] = "mysql" if self.route == "mysql" else self.route
            body["sql"] = self.sql
            body["params"] = list(self.params)
        if self.url:
            body["url"] = self.url
            body["method"] = self.method
        if self.credential_ref:
            body["credential_ref"] = self.credential_ref
        if self.raw_plan:
            query = self.raw_plan.get("query")
            body["dialect"] = query.get("dialect") if isinstance(query, dict) else self.route
            body["query"] = query
        return body
