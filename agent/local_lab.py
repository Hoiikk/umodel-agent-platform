"""Stand-ins for UModel and MySQL when Docker is not running.

Open-source UModel refuses a plain .entity_set read. This HTTP server returns that
same refusal. The MySQL stand-in answers the SELECT the connector then renders:
one candidate id, one status, one position, or one opening id. Other SQL is rejected.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mysql_mimic import MysqlServer, Session, User
from mysql_mimic.auth import IdentityProvider, NativePasswordAuthPlugin
from mysql_mimic.errors import MysqlError

from data_agent.agent import load_local_env

_ID = re.compile(r"`id`\s*=\s*'([A-Za-z0-9_-]+)'")
_STATUS = re.compile(r"`status`\s*=\s*'(APPLIED|SCREENING|INTERVIEWING|HIRED|REJECTED)'")
_POSITION = re.compile("`position`\\s*=\\s*'([\u4e00-\u9fffA-Za-z0-9]{1,32})'")
_COLUMNS = ("id", "name", "phone", "email", "position", "status", "source", "reject_reason", "created_at")
_OPENING_COLUMNS = ("id", "title", "headcount")
_OPENINGS = {
    "job-001": ("job-001", "前端工程师", 2),
    "job-002": ("job-002", "后端工程师", 1),
    "job-003": ("job-003", "测试工程师", 1),
    "job-004": ("job-004", "产品经理", 1),
}
_ROWS = {
    "cand-001": (
        "cand-001", "张伟", "13800000001", "zhangwei@example.com",
        "前端工程师", "APPLIED", "BOSS直聘", None, "2026-09-10 09:30:00.000",
    ),
    "cand-002": (
        "cand-002", "李娜", "13800000002", "lina@example.com",
        "后端工程师", "APPLIED", "官网投递", None, "2026-09-12 14:05:00.000",
    ),
    "cand-003": (
        "cand-003", "王强", "13800000003", "wangqiang@example.com",
        "测试工程师", "SCREENING", "拉勾网", None, "2026-09-08 10:20:00.000",
    ),
    "cand-004": (
        "cand-004", "陈静", "13800000004", "chenjing@example.com",
        "前端工程师", "INTERVIEWING", "内推", None, "2026-09-05 16:45:00.000",
    ),
    "cand-005": (
        "cand-005", "刘洋", "13800000005", "liuyang@example.com",
        "后端工程师", "HIRED", "猎聘", None, "2026-08-28 11:00:00.000",
    ),
    "cand-006": (
        "cand-006", "赵敏", "13800000006", "zhaomin@example.com",
        "产品经理", "REJECTED", "猎头推荐", "技能不匹配", "2026-09-01 08:50:00.000",
    ),
    "cand-007": (
        "cand-007", "周宁", "13800000007", "zhouning@example.com",
        "前端工程师", "HIRED", "猎聘", None, "2026-08-20 10:15:00.000",
    ),
    "cand-008": (
        "cand-008", "吴婷", "13800000008", "wuting@example.com",
        "后端工程师", "INTERVIEWING", "内推", None, "2026-09-15 09:10:00.000",
    ),
}
_REFUSAL = {
    "error": {
        "code": "QUERY_PLAN_ERROR",
        "message": ".entity_set requires entity-call",
    }
}


class _UModelHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length).decode() or "{}")
        except json.JSONDecodeError:
            body = {}
        query = str(body.get("query") or "")
        if query.strip().startswith(".entity_set"):
            payload = _REFUSAL
        else:
            payload = {
                "error": {
                    "code": "QUERY_PLAN_ERROR",
                    "message": "local stand-in only serves .entity_set lookups",
                }
            }
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[umodel] {self.path} {fmt % args}")


class _Reader(IdentityProvider):
    def __init__(self, password: str) -> None:
        self._auth = NativePasswordAuthPlugin.create_auth_string(password)

    async def get_user(self, username: str) -> User | None:
        if username != "umodel_reader":
            return None
        return User(name=username, auth_string=self._auth, auth_plugin=NativePasswordAuthPlugin.name)


class _Candidates(Session):
    async def query(self, expression: object, sql: str, attrs: dict[str, str]) -> tuple[list[tuple], list[str]]:
        text = sql or ""
        by_id = _ID.search(text)
        by_status = _STATUS.search(text)
        by_position = _POSITION.search(text)
        if "`openings`" in text:
            if by_id is None or by_status or by_position or "`candidates`" in text:
                raise MysqlError("local stand-in only serves one opening id")
            row = _OPENINGS.get(by_id.group(1))
            return ([row] if row else []), list(_OPENING_COLUMNS)
        found = [item for item in (by_id, by_status, by_position) if item]
        if len(found) != 1 or "`candidates`" not in text:
            raise MysqlError("local stand-in only serves one candidate lookup or one status/position filter")
        if by_id:
            row = _ROWS.get(by_id.group(1))
            return ([row] if row else []), list(_COLUMNS)
        picked = by_status or by_position
        column = 5 if by_status else 4
        assert picked is not None
        return [row for row in _ROWS.values() if row[column] == picked.group(1)], list(_COLUMNS)


def main() -> None:
    load_local_env()
    password = os.environ.get("RMS_READONLY_PASSWORD") or ""
    if not password:
        raise SystemExit("rms/.env 里没有 RMS_READONLY_PASSWORD")
    httpd = ThreadingHTTPServer(("127.0.0.1", 8080), _UModelHandler)
    httpd.daemon_threads = True
    print("UModel stand-in http://127.0.0.1:8080", flush=True)
    print("MySQL stand-in 127.0.0.1:3308 user umodel_reader", flush=True)
    import threading

    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    server = MysqlServer(session_factory=_Candidates, identity_provider=_Reader(password))
    asyncio.run(server.serve_forever(host="127.0.0.1", port=3308))


if __name__ == "__main__":
    main()
