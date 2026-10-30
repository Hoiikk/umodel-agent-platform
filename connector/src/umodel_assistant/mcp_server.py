"""MCP entry for this fetch layer.

Open-source UModel names the missing executor umodel-assistant and does not
ship its source. This process is a local implementation of that gap, not a
copy of unpublished code and not a rewrite of official umodel-mcp. Tool names
match the query subset. Graph SPL still goes to Go. Business .entity_set
reads use the local model pack.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from .auth_context import Principal, authenticate
from .dispatch import Assistant, example_queries
from .errors import AssistantError

SERVER_NAME = "umodel-assistant-py"
SERVER_VERSION = "0.3.0"
PROTOCOL_VERSION = "2025-06-18"

EXECUTE_DESCRIPTION = (
    "Execute unified SPL. Default mode=data. "
    ".umodel / .entity / .topo are read from open-source UModel. "
    ".entity_set with ids=['...'] is rendered from the model pack "
    "(MySQL parameters stay bound; HTTP URLs must match the allowlist) "
    "and executed when mode=data. mode=plan returns the plan only. "
    "get_metrics / get_logs execute the Go plan's PromQL, Elasticsearch, or ClickHouse query. "
    "A passthrough plan or a missing secret fails instead of returning sample rows."
)
EXPLAIN_DESCRIPTION = (
    "Explain SPL by calling open-source UModel /explain. "
    "This does not build or run the local fetch plan."
)

TOOLS: list[dict[str, Any]] = [
    {
        "name": "query_spl_execute",
        "description": EXECUTE_DESCRIPTION,
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "SPL text"},
                "workspace": {
                    "type": "string",
                    "description": "Leave empty to use UMODEL_WORKSPACE. Any other value is rejected.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["data", "plan"],
                    "default": "data",
                },
            },
        },
    },
    {
        "name": "query_spl_explain",
        "description": EXPLAIN_DESCRIPTION,
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string"},
                "workspace": {
                    "type": "string",
                    "description": "Leave empty to use UMODEL_WORKSPACE. Any other value is rejected.",
                },
            },
        },
    },
    {
        "name": "query_spl_examples",
        "description": "Safe SPL examples including the commerce live-fetch demo.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def call_tool(
    name: str,
    arguments: dict[str, Any] | None = None,
    workspace: str = "demo",
    assistant: Assistant | None = None,
    principal: Principal | None = None,
) -> dict[str, Any]:
    arguments = arguments or {}
    try:
        asst = assistant or Assistant()
    except ValueError as exc:
        return {"ok": False, "code": "config", "error": str(exc)}
    query = str(arguments.get("query") or arguments.get("spl") or "").strip()
    requested = str(arguments.get("workspace") or workspace or "")
    if requested and requested != asst.settings.workspace:
        return {"ok": False, "code": "workspace", "error": "workspace is fixed by UMODEL_WORKSPACE for this process"}
    if name == "query_spl_examples":
        return {"ok": True, "examples": example_queries()}
    try:
        caller = principal or authenticate(asst.settings)
    except AssistantError as exc:
        return exc.as_dict()
    if name == "query_spl_explain":
        if not query:
            return {"ok": False, "error": "query argument is required"}
        return asst.explain(query)
    if name == "query_spl_execute":
        if not query:
            return {"ok": False, "error": "query argument is required"}
        mode = str(arguments.get("mode") or "data")
        return asst.execute_sync(query, mode, caller)
    return {"ok": False, "error": f"unknown tool {name!r}"}


def mcp_content(payload: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False)
    is_error = not bool(payload.get("ok", True))
    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
        "structuredContent": payload,
    }


def handle_rpc(
    message: dict[str, Any],
    assistant: Assistant | None = None,
    default_workspace: str = "demo",
    principal: Principal | None = None,
) -> dict[str, Any] | None:
    method = str(message.get("method") or "")
    req_id = message.get("id")
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    workspace = str(params.get("workspace") or default_workspace)

    if method in {"notifications/initialized", "notifications/cancelled"}:
        return None
    if method in {"ping", "logging/setLevel"}:
        return _rpc_result(req_id, {})
    if method == "initialize":
        return _rpc_result(
            req_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
    if method == "tools/list":
        return _rpc_result(req_id, {"tools": TOOLS})
    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        payload = call_tool(name, arguments, workspace=workspace, assistant=assistant, principal=principal)
        return _rpc_result(req_id, mcp_content(payload))
    if method in {"resources/list", "prompts/list"}:
        key = "resources" if method.startswith("resources") else "prompts"
        return _rpc_result(req_id, {key: []})
    if not method:
        return _rpc_error(req_id, -32600, "Invalid request")
    return _rpc_error(req_id, -32601, f"Method not found: {method}")


def _rpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _rpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def serve_ndjson(
    assistant: Assistant | None = None,
    default_workspace: str = "demo",
) -> None:
    asst = assistant or Assistant()
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            sys.stdout.write(json.dumps(_rpc_error(None, -32700, str(exc)), ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue
        if not isinstance(message, dict):
            continue
        reply = handle_rpc(message, assistant=asst, default_workspace=default_workspace)
        if reply is None:
            continue
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def build_fastmcp():
    server_cls = None
    try:
        from mcp.server.mcpserver import MCPServer

        server_cls = MCPServer
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP

            server_cls = FastMCP
        except ImportError:
            return None

    server = server_cls(SERVER_NAME)

    @server.tool(name="query_spl_execute", description=EXECUTE_DESCRIPTION)
    def query_spl_execute(
        query: str,
        workspace: str = "",
        mode: str = "data",
    ) -> dict[str, Any]:
        return call_tool(
            "query_spl_execute",
            {"query": query, "workspace": workspace, "mode": mode},
            workspace=workspace,
        )

    @server.tool(
        name="query_spl_explain",
        description=EXPLAIN_DESCRIPTION,
    )
    def query_spl_explain(query: str, workspace: str = "") -> dict[str, Any]:
        return call_tool(
            "query_spl_explain",
            {"query": query, "workspace": workspace},
            workspace=workspace,
        )

    @server.tool(
        name="query_spl_examples",
        description="Safe SPL examples including the commerce live-fetch demo.",
    )
    def query_spl_examples() -> dict[str, Any]:
        return call_tool("query_spl_examples", {})

    return server


_DEMO_ORDERS = ".entity_set with(domain='commerce', name='commerce.order', ids=['U-1001'])"


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    default_workspace = os.environ.get("UMODEL_WORKSPACE", "demo")
    if "--self-test" in args:
        # Renders the model-pack plan only. Live rows need Go plus credential_ref.
        os.environ.setdefault("UMODEL_AUTH_MODE", "dev_header")
        os.environ.setdefault("UMODEL_DEV_USER", "self-test")
        try:
            assistant = Assistant()
            caller = authenticate(assistant.settings)
            plan = assistant.renderer.render_spl(_DEMO_ORDERS, caller)
            assistant.guard.validate_sql(plan.sql)
        except (AssistantError, ValueError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
            raise SystemExit(1) from exc
        if "U-1001" in plan.sql or plan.params[0] != "U-1001":
            print(json.dumps({"ok": False, "error": "entity id was interpolated into SQL"}, ensure_ascii=False))
            raise SystemExit(1)
        payload = {"ok": True, "mode": "plan", "route": plan.route, "plan": plan.public()}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    want_ndjson = "--ndjson" in args
    server = build_fastmcp()
    transport = "stdio MCP" if server is not None and not want_ndjson else "newline JSON-RPC"
    _log(
        f"{SERVER_NAME} {SERVER_VERSION} waiting on stdin ({transport}, "
        f"workspace={default_workspace}). This process has no prompt; "
        "Ctrl+C to stop. Smoke test: python mcp_server.py --self-test"
    )
    if server is not None and not want_ndjson:
        server.run()
        return
    if server is None:
        _log("mcp package is not installed; pip install mcp for Cursor / Claude Desktop.")
    serve_ndjson(default_workspace=default_workspace)


if __name__ == "__main__":
    main()
