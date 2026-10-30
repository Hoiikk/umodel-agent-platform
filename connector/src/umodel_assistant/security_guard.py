"""Check renderer output and outbound URLs. This does not accept SQL written by the agent."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from .errors import AssistantError

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|grant|revoke|truncate|outfile|load_file)\b",
    re.IGNORECASE,
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_METADATA_HOSTS = {"169.254.169.254", "metadata.google.internal"}


class SecurityGuard:
    def validate_sql(self, sql: str) -> str:
        text = (sql or "").strip()
        if text.endswith(";"):
            text = text[:-1].strip()
        if not text or ";" in text or "--" in text or "/*" in text:
            raise AssistantError("sql_rejected", "SQL must be one read-only statement")
        head = text.lstrip("(").lower()
        if not (head.startswith("select") or head.startswith("with")):
            raise AssistantError("sql_rejected", "SQL must start with SELECT or WITH")
        if _FORBIDDEN.search(text):
            raise AssistantError("sql_rejected", "SQL contains a statement that is not read-only")
        return text

    def require_safe_id(self, entity_id: str) -> str:
        value = (entity_id or "").strip()
        if not _SAFE_ID.fullmatch(value) or ".." in value:
            raise AssistantError("unsafe_id", f"unsafe entity id: {entity_id!r}")
        return value

    def quote_ident(self, name: str) -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name or ""):
            raise AssistantError("unsafe_ident", f"unsafe SQL identifier: {name!r}")
        return f"`{name}`"

    def validate_http_url(self, url: str, allowed_hosts: frozenset[str]) -> str:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
            raise AssistantError("ssrf", f"refusing URL {url!r}")
        if host in _METADATA_HOSTS or _link_local(host):
            raise AssistantError("ssrf", f"refusing metadata or link-local host {host}")
        port = parsed.port
        if host in {"127.0.0.1", "localhost", "::1"}:
            if port is None or f"{host}:{port}" not in allowed_hosts:
                raise AssistantError("ssrf", f"loopback URL must match an allowlist host:port, got {host}")
            return url
        if host in allowed_hosts or (port is not None and f"{host}:{port}" in allowed_hosts):
            return url
        raise AssistantError("ssrf", f"host {host} is not in the outbound allowlist")


def sanitize_log_text(text: str) -> str:
    redacted = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*", r"\1***", text)
    redacted = re.sub(r"(?i)(password|token|secret)=([^&\s]+)", r"\1=***", redacted)
    return redacted


def _link_local(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_link_local
    except ValueError:
        return False
