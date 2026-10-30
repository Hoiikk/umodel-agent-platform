"""Authenticated callers may read entity sets present in the model pack.

project() drops columns the event set does not declare. Tenant predicates are
added by the renderer only when the storage spec sets tenant_field.
"""

from __future__ import annotations

from .auth_context import Principal
from .errors import AssistantError


class Policy:
    def __init__(self, entity_sets: set[str], event_fields: dict[str, frozenset[str]]) -> None:
        self.entity_sets = entity_sets
        self.event_fields = event_fields

    def allow_graph(self, principal: Principal) -> None:
        _require(principal)

    def allow_entity(self, principal: Principal, name: str) -> None:
        _require(principal)
        if name not in self.entity_sets:
            raise AssistantError("forbidden", f"entity set {name} is not in the model pack")

    def project(self, rows: list[dict], allowed: frozenset[str] | None) -> list[dict]:
        if allowed is None:
            return rows
        return [{key: value for key, value in row.items() if key in allowed} for row in rows]


def _require(principal: Principal) -> None:
    if principal is None or not principal.user_id:
        raise AssistantError("unauthenticated", "a caller identity is required")
