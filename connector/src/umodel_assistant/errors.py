"""Failures the assistant returns to the agent. Missing integrations raise, they do not invent data."""

from __future__ import annotations


class AssistantError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict[str, object]:
        body: dict[str, object] = {"ok": False, "code": self.code, "error": self.message}
        if self.details:
            body["details"] = self.details
        return body


class NotConfigured(AssistantError):
    def __init__(self, component: str, required: list[str]) -> None:
        joined = ", ".join(required)
        super().__init__(
            "not_configured",
            f"{component} is not configured; provide {joined}",
            {"component": component, "required": joined},
        )
