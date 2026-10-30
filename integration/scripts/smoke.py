"""Local contract smoke test for UModel → Connector → RMS MySQL."""

from __future__ import annotations

import json

from umodel_assistant.auth_context import Principal
from umodel_assistant.config import load_settings
from umodel_assistant.dispatch import Assistant


def main() -> None:
    query = ".entity_set with(domain='rms', name='rms.candidate', ids=['cand-001'])"
    result = Assistant(load_settings()).execute_sync(query, "data", Principal("smoke-agent", "local"))
    assert result.get("ok") is True, result
    assert result.get("route") == "mysql", result
    rows = result.get("data")
    assert isinstance(rows, list) and len(rows) == 1, result
    row = rows[0]
    assert row["candidate_id"] == "cand-001", row
    assert row["name"] == "张*", row
    assert row["phone"] == "138****0001", row
    assert row["email"] == "z***@example.com", row
    assert row["status"] == "APPLIED", row
    print(json.dumps({"ok": True, "route": result["route"], "candidate_id": row["candidate_id"], "status": row["status"]}))


if __name__ == "__main__":
    main()
