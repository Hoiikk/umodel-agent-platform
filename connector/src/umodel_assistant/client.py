"""REST client for open-source UModel. execute() always sends mode=plan."""

from __future__ import annotations

from typing import Any

import httpx

from .config import Settings
from .errors import AssistantError


class UModelClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute_url(self) -> str:
        return f"{self.settings.go_addr}/api/v1/query/{self.settings.workspace}/execute"

    def explain_url(self) -> str:
        return f"{self.settings.go_addr}/api/v1/query/{self.settings.workspace}/explain"

    def execute(self, spl: str) -> dict[str, Any]:
        return self._post(self.execute_url(), spl)

    def explain(self, spl: str) -> dict[str, Any]:
        return self._post(self.explain_url(), spl)

    def _post(self, url: str, spl: str) -> dict[str, Any]:
        payload = {"query": spl, "mode": "plan", "format": "agent", "include_spec": True}
        try:
            response = httpx.post(url, json=payload, timeout=self.settings.timeout)
        except httpx.ConnectError as exc:
            raise AssistantError(
                "go_unreachable",
                f"UModel is not reachable at {url}. Start the open-source server with: go run ./cmd/umodel-server",
            ) from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise AssistantError("go_bad_response", "UModel returned a non-JSON body") from exc
        if not isinstance(body, dict):
            raise AssistantError("go_bad_response", f"unexpected UModel response type: {type(body).__name__}")
        return body
