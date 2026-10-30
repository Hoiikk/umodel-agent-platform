"""Process configuration. Identity and secrets come from the environment, never from tool arguments."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_PACKAGE_MODEL_ROOT = Path(__file__).resolve().parent / "model"
_PROJECT_MODEL_ROOT = Path(__file__).resolve().parents[2] / "model"
_MODEL_ROOT = _PACKAGE_MODEL_ROOT if _PACKAGE_MODEL_ROOT.is_dir() else _PROJECT_MODEL_ROOT
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True, slots=True)
class Settings:
    go_addr: str = "http://localhost:8080"
    workspace: str = "demo"
    allowed_hosts: frozenset[str] = frozenset({"127.0.0.1:8001"})
    max_sql_limit: int = 1000
    audit: bool = True
    secret_provider: str = "env"
    auth_mode: str = "deny"
    model_root: Path = _MODEL_ROOT
    timeout: float = 30.0


def load_settings() -> Settings:
    hosts = _hosts(os.environ.get("ALLOWED_HTTP_HOSTS", "127.0.0.1:8001"))
    provider = os.environ.get("SECRET_PROVIDER_TYPE", "env").strip().lower()
    if provider not in {"env", "vault", "kms"}:
        provider = "env"
    auth_mode = os.environ.get("UMODEL_AUTH_MODE", "deny").strip().lower()
    if auth_mode not in {"deny", "dev_header"}:
        auth_mode = "deny"
    return Settings(
        go_addr=os.environ.get("UMODEL_ADDR", "http://localhost:8080").rstrip("/"),
        workspace=os.environ.get("UMODEL_WORKSPACE", "demo"),
        allowed_hosts=hosts,
        max_sql_limit=_positive(os.environ.get("MAX_SQL_LIMIT"), 1000),
        audit=os.environ.get("ENABLE_AUDIT_LOG", "1") not in {"0", "false", "False"},
        secret_provider=provider,
        auth_mode=auth_mode,
        timeout=float(os.environ.get("UMODEL_TIMEOUT", "30")),
    )


def _hosts(raw: str) -> frozenset[str]:
    items = {part.strip().lower() for part in raw.split(",") if part.strip()}
    # A bare loopback host would allow every local port. Require host:port.
    bare = items & _LOOPBACK
    if bare:
        raise ValueError(f"loopback allowlist entries need a port, got {sorted(bare)}")
    return items or frozenset({"127.0.0.1:8001"})


def _positive(raw: str | None, default: int) -> int:
    if not raw:
        return default
    value = int(raw)
    if value < 1:
        raise ValueError("MAX_SQL_LIMIT must be positive")
    return value
