"""Structured access log. A remote bus is wired only when its client exists."""

from __future__ import annotations

import json
import logging
import sys

from .errors import NotConfigured
from .security_guard import sanitize_log_text

_LOG = logging.getLogger("umodel.assistant.audit")


def log_access(record: dict[str, object], *, enabled: bool = True) -> None:
    if not enabled:
        return
    _ensure_handler()
    safe: dict[str, object] = {}
    for key, value in record.items():
        safe[key] = sanitize_log_text(value) if isinstance(value, str) else value
    _LOG.info("%s", json.dumps(safe, ensure_ascii=False, default=str))


def _ensure_handler() -> None:
    if _LOG.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _LOG.addHandler(handler)
    _LOG.setLevel(logging.INFO)
    _LOG.propagate = False


def push_remote(record: dict[str, object]) -> None:
    # ENTERPRISE_HOOK: send `record` to the company audit bus (Kafka, SLS, or ES).
    # Keep the payload produced by log_access; do not add SQL literals or secrets.
    raise NotConfigured("audit bus", ["AUDIT_BOOTSTRAP"])
