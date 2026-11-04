from __future__ import annotations

import json

import httpx
import pytest

from tests.support.mock_backends import app
from umodel_assistant.auth_context import Principal, authenticate
from umodel_assistant.config import Settings
from umodel_assistant.data_masker import mask_rows
from umodel_assistant.dispatch import Assistant, rename_rows
from umodel_assistant.errors import NotConfigured
from umodel_assistant.executors.base import FetchPlan
from umodel_assistant.mcp_server import TOOLS, call_tool, handle_rpc, main
from umodel_assistant.plan_normalize import normalize
from umodel_assistant.plan_validate import route_plan
from umodel_assistant.secret_resolver import SecretResolver
from umodel_assistant.security_guard import SecurityGuard

PRINCIPAL = Principal("tester", "acme")
ORDERS = ".entity_set with(domain='commerce', name='commerce.order', ids=['U-1001'])"
USERS = ".entity_set with(domain='commerce', name='commerce.user', ids=['U-1001'])"
PAYMENTS = ".entity_set with(domain='commerce', name='commerce.payment', ids=['P-3001'])"
RMS_CANDIDATE = ".entity_set with(domain='rms', name='rms.candidate', ids=['cand-001'])"
SETTINGS = Settings()


def _assistant(body: dict, mysql_runner=None, http_client=None) -> Assistant:
    class _Go:
        def execute(self, spl: str) -> dict:
            return body

        def explain(self, spl: str) -> dict:
            return {"source": ".umodel", "query": spl}

    return Assistant(settings=SETTINGS, go=_Go(), mysql_runner=mysql_runner, http_client=http_client)


def test_normalize_matrix_plan_and_error() -> None:
    rows = normalize({"code": "200", "data": {"header": ["name"], "data": [["from-go"]]}})
    assert rows.kind == "rows" and rows.rows == [{"name": "from-go"}]
    plan = {"mode": "plan", "query": {"dialect": "prometheus_promql"}}
    wrapped = normalize(
        {
            "data": {
                "header": ["responseType", "query", "header", "data"],
                "data": [[1, json.dumps(plan), [], []]],
            }
        }
    )
    assert wrapped.kind == "plan" and wrapped.plan == plan
    assert normalize({"mode": "plan", "query": {"dialect": "elasticsearch_dsl"}}).kind == "plan"
    error = normalize({"error": {"code": "NOT_IMPLEMENTED", "message": "use assistant"}})
    assert error.kind == "error" and error.code == "NOT_IMPLEMENTED"


def test_render_binds_order_id_and_rejects_injection() -> None:
    assistant = _assistant({})
    plan = assistant.renderer.render_spl(ORDERS, PRINCIPAL)
    assert "U-1001" not in plan.sql
    assert plan.params == ("U-1001",)
    assert plan.sql.startswith("SELECT ")
    with pytest.raises(Exception, match="unsafe entity id"):
        assistant.renderer.render_spl(
            ".entity_set with(domain='commerce', name='commerce.order', ids=['U-1; DROP'])",
            PRINCIPAL,
        )
    with pytest.raises(Exception, match="unsafe entity id"):
        assistant.renderer.render_spl(
            ".entity_set with(domain='commerce', name='commerce.order', ids=['a..b'])",
            PRINCIPAL,
        )


def test_rms_status_filter_is_one_bound_parameter() -> None:
    plan = _assistant({}).renderer.render_spl(
        ".entity_set with(domain='rms', name='rms.candidate', status='HIRED')",
        PRINCIPAL,
    )
    assert "HIRED" not in plan.sql
    assert plan.params == ("HIRED",)
    assert "`status` = %s" in plan.sql
    with pytest.raises(Exception, match="filter must be one candidate status or one position"):
        _assistant({}).renderer.render_spl(
            ".entity_set with(domain='rms', name='rms.candidate', status='OFFER')",
            PRINCIPAL,
        )


def test_rms_storage_endpoint_can_be_overridden_for_a_deployment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RMS_MYSQL_ENDPOINT", "127.0.0.1:3308")
    plan = _assistant({}).renderer.render_spl(RMS_CANDIDATE, PRINCIPAL)
    assert plan.mysql_target == {
        "host": "127.0.0.1",
        "port": 3308,
        "database": "rms",
        "username": "umodel_reader",
    }


def test_guard_rejects_writes_multistatement_and_ssrf() -> None:
    guard = SecurityGuard()
    with pytest.raises(Exception, match="SELECT or WITH"):
        guard.validate_sql("DELETE FROM t_order")
    with pytest.raises(Exception, match="one read-only"):
        guard.validate_sql("SELECT 1; SELECT 2")
    with pytest.raises(Exception, match="metadata|link-local|refusing"):
        guard.validate_http_url("http://169.254.169.254/latest", SETTINGS.allowed_hosts)
    with pytest.raises(Exception, match="allowlist|loopback"):
        guard.validate_http_url("http://127.0.0.1:3306/", SETTINGS.allowed_hosts)


def test_secrets_and_auth_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMMERCE_MYSQL_PASSWORD", raising=False)
    with pytest.raises(NotConfigured):
        SecretResolver("env").resolve("secret://COMMERCE_MYSQL_PASSWORD")
    with pytest.raises(NotConfigured, match="VAULT_ADDR"):
        SecretResolver("vault").resolve("secret://db")
    monkeypatch.delenv("UMODEL_DEV_USER", raising=False)
    monkeypatch.setenv("UMODEL_AUTH_MODE", "deny")
    with pytest.raises(Exception, match="authentication is required"):
        authenticate(Settings(auth_mode="deny"))
    with pytest.raises(Exception, match="UMODEL_DEV_USER"):
        authenticate(Settings(auth_mode="dev_header"))


def test_passthrough_clickhouse_is_not_mysql() -> None:
    called: list[str] = []

    async def runner(plan: FetchPlan) -> list[dict]:
        called.append(plan.sql)
        return []

    body = {"mode": "plan", "query": {"dialect": "clickhouse"}, "data_source": {"storage": {"type": "clickhouse"}}}
    out = _assistant(body, mysql_runner=runner).execute_sync(ORDERS, "data", PRINCIPAL)
    assert out["ok"] is False
    assert out["code"] == "passthrough"
    assert called == []
    with pytest.raises(Exception, match="no executable query"):
        route_plan(body)


def test_promql_without_endpoint_fails() -> None:
    body = {
        "mode": "plan",
        "query": {"dialect": "prometheus_promql", "queries": [{"promql": "up"}]},
        "data_source": {"storage": {"type": "prometheus"}},
    }
    out = _assistant(body).execute_sync(".entity_set with(domain='devops', name='devops.service')", "data", PRINCIPAL)
    assert out["ok"] is False
    assert out["code"] == "not_runnable"


def test_graph_rows_do_not_touch_mysql() -> None:
    called: list[str] = []

    async def runner(plan: FetchPlan) -> list[dict]:
        called.append("mysql")
        return []

    body = {"code": "200", "data": {"header": ["name"], "data": [["from-go"]]}}
    out = _assistant(body, mysql_runner=runner).execute_sync(
        ".entity with(domain='commerce') | limit 1", "data", PRINCIPAL
    )
    assert out["route"] == "graph"
    assert out["data"] == [{"name": "from-go"}]
    assert called == []


def test_order_plan_and_bound_execution() -> None:
    seen: dict[str, object] = {}

    async def runner(plan: FetchPlan) -> list[dict]:
        seen["params"] = plan.params
        seen["sql"] = plan.sql
        return [
            {
                "order_id": "O-2001",
                "user_id": "U-1001",
                "amount": "128.00",
                "status": "open",
                "created_at": "2026-10-20 10:00:00",
                "secret_note": "nope",
            }
        ]

    go_error = {"error": {"code": "QUERY_PLAN_ERROR", "message": ".entity_set requires entity-call"}}
    assistant = _assistant(go_error, mysql_runner=runner)
    planned = assistant.execute_sync(ORDERS, "plan", PRINCIPAL)
    assert planned["ok"] is True
    assert planned["route"] == "mysql"
    assert "data" not in planned
    assert seen == {}
    fetched = assistant.execute_sync(ORDERS, "data", PRINCIPAL)
    assert fetched["data"][0]["order_id"] == "O-2001"
    assert "secret_note" not in fetched["data"][0]
    assert seen["params"] == ("U-1001",)


def test_entity_read_fallback_accepts_current_umodel_parse_error() -> None:
    async def runner(plan: FetchPlan) -> list[dict]:
        return [{"order_id": "O-2001", "user_id": "U-1001", "amount": "128.00", "status": "open", "created_at": "now"}]

    body = {
        "error": {
            "code": "QUERY_PARSE_ERROR",
            "message": ".entity_set requires entity-call __list_method__()",
        }
    }
    out = _assistant(body, mysql_runner=runner).execute_sync(ORDERS, "data", PRINCIPAL)
    assert out["ok"] is True
    assert out["route"] == "mysql"


def test_user_http_masks_tagged_name() -> None:
    import asyncio

    go_error = {"error": {"code": "QUERY_PLAN_ERROR", "message": ".entity_set requires entity-call"}}

    async def run() -> dict:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8001") as client:
            return await _assistant(go_error, http_client=client).execute(USERS, "data", PRINCIPAL)

    out = asyncio.run(run())
    assert out["ok"] is True, out
    assert out["data"][0]["name"] == "张*"
    assert out["data"][0]["user_id"] == "U-1001"


def test_payment_http_reads_payment_system() -> None:
    import asyncio

    go_error = {"error": {"code": "QUERY_PLAN_ERROR", "message": ".entity_set requires entity-call"}}

    async def run() -> dict:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8001") as client:
            return await _assistant(go_error, http_client=client).execute(PAYMENTS, "data", PRINCIPAL)

    out = asyncio.run(run())
    assert out["ok"] is True, out
    assert out["route"] == "http"
    assert out["data"][0]["payment_id"] == "P-3001"
    assert out["data"][0]["order_id"] == "O-2001"
    assert "/api/payments/P-3001" in out["plan"]["url"]


def test_rename_maps_storage_column_to_field() -> None:
    assert rename_rows([{"uid": "U-1001"}], {"user_id": "uid"}) == [{"user_id": "U-1001"}]


def test_storage_failure_is_an_error() -> None:
    async def runner(plan: FetchPlan) -> list[dict]:
        raise RuntimeError("connection refused")

    go_error = {"error": {"code": "QUERY_PLAN_ERROR", "message": ".entity_set requires entity-call"}}
    out = _assistant(go_error, mysql_runner=runner).execute_sync(ORDERS, "data", PRINCIPAL)
    assert out["ok"] is False
    assert out["code"] == "storage_error"


def test_mask_ignores_untagged_values() -> None:
    rows = mask_rows([{"name": "张三", "status": "张三"}], {"name": "pii.name"})
    assert rows == [{"name": "张*", "status": "张三"}]


def test_go_not_implemented_is_returned() -> None:
    body = {"error": {"code": "NOT_IMPLEMENTED", "message": "unified-model only supports mode=plan"}}
    out = _assistant(body).execute_sync(".umodel | limit 1", "data", PRINCIPAL)
    assert out["code"] == "NOT_IMPLEMENTED"


def test_mcp_requires_identity_and_lists_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UMODEL_DEV_USER", raising=False)
    denied = call_tool("query_spl_execute", {"query": ORDERS}, assistant=_assistant({}))
    assert denied["code"] == "unauthenticated"
    listed = handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, assistant=_assistant({}))
    assert [tool["name"] for tool in listed["result"]["tools"]] == [item["name"] for item in TOOLS]


def test_self_test_prints_bound_plan(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UMODEL_DEV_USER", raising=False)
    monkeypatch.delenv("UMODEL_AUTH_MODE", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["--self-test"])
    assert exc.value.code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["plan"]["params"] == ["U-1001"]
    assert "U-1001" not in printed["plan"]["sql"]
