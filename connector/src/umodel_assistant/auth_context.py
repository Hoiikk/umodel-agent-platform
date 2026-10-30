"""Caller identity. The agent tool payload cannot supply this."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .config import Settings
from .errors import AssistantError, NotConfigured


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()


def authenticate(settings: Settings) -> Principal:
    if settings.auth_mode == "dev_header":
        # ENTERPRISE_HOOK: replace this branch with JWT/OIDC or mTLS verification.
        # Read the credential from the gateway, not from the tool arguments.
        user = os.environ.get("UMODEL_DEV_USER", "").strip()
        if not user:
            raise AssistantError("unauthenticated", "UMODEL_DEV_USER is required when UMODEL_AUTH_MODE=dev_header")
        return Principal(user_id=user, tenant_id=os.environ.get("UMODEL_DEV_TENANT", "").strip())
    if settings.auth_mode == "deny":
        raise AssistantError(
            "unauthenticated",
            "authentication is required; set UMODEL_AUTH_MODE=dev_header for local development",
        )
    raise NotConfigured("auth", ["UMODEL_AUTH_MODE"])
