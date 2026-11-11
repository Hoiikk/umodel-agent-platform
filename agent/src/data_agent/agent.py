"""ReAct loop over one read-only UModel tool. No agent framework."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

MAX_STEPS = 5
DEFAULT_GOAL = "比较 cand-004 和 cand-005，谁在招聘流程里更靠后？只根据查到的状态回答。"
_PREFIX = r"^\.entity_set with\(domain='rms', name='rms\.candidate', "
_SPL_PATTERNS = (
    re.compile(_PREFIX + r"ids=\['[A-Za-z0-9_-]+'\]\)$"),
    re.compile(_PREFIX + r"status='(?:APPLIED|SCREENING|INTERVIEWING|HIRED|REJECTED)'\)$"),
    re.compile(_PREFIX + "position='[\u4e00-\u9fffA-Za-z0-9]{1,32}'\\)$"),
)
_SPL_HELP = (
    ".entity_set with(domain='rms', name='rms.candidate', ids=['cand-001'])；"
    "或把 ids 换成 status='HIRED'、position='前端工程师'。一次只能填其中一种。"
)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_umodel",
            "description": "按一个编号、一个状态或一个职位查询招聘记录。SPL 必须是规定格式。",
            "parameters": {
                "type": "object",
                "properties": {"spl_query": {"type": "string", "description": _SPL_HELP}},
                "required": ["spl_query"],
            },
        },
    }
]
SYSTEM = """你是招聘数据助手。只能通过 query_umodel 查数据。
SPL 只能是下面三种之一，一次只能填一种：
.entity_set with(domain='rms', name='rms.candidate', ids=['某个编号'])
.entity_set with(domain='rms', name='rms.candidate', status='HIRED')
.entity_set with(domain='rms', name='rms.candidate', position='前端工程师')
status 只能是 APPLIED、SCREENING、INTERVIEWING、HIRED、REJECTED。
用户给了编号就用 ids。没给编号、按状态或职位发问时，用 status 或 position。
返回字段只有 candidate_id、name、phone、email、position、status、source、reject_reason、created_at。
status 的含义是 APPLIED 已投递、SCREENING 筛选中、INTERVIEWING 面试中、HIRED 已录用、REJECTED 已淘汰。
姓名、电话、邮箱已经打码。没有面试评价。
reject_reason 是淘汰原因。它是空值就写没有这项数据，不要根据状态编造原因。
返回几行就写几行。ok 不是 true，或 data 为空，表示没查到。不要编造没有返回的人或数字。
没有查询全部候选人的语句，不要把几次查询的行数相加当成总人数。
前进顺序是已投递、筛选中、面试中、已录用。已淘汰不能和仍在流程中的人比先后。
材料够了就直接写结论，不要再调用工具。"""

Complete = Callable[[list[dict], list[dict]], dict]
Query = Callable[[str], str]


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "integration" / "compose.yaml").is_file():
            return candidate
    raise RuntimeError("repo root not found from data_agent")


def apply_env_file(path: Path) -> None:
    """Fill unset variables. Existing process environment wins."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def load_local_env() -> None:
    root = repo_root()
    apply_env_file(root / "agent" / ".env")
    apply_env_file(root / "rms" / ".env")


def query_umodel(spl_query: str, execute: Query | None = None) -> str:
    spl = (spl_query or "").strip()
    if not any(pattern.match(spl) for pattern in _SPL_PATTERNS):
        payload = {"ok": False, "error": "只接受 rms.candidate 的一个编号、一个状态或一个职位"}
    else:
        payload = (execute or _execute)(spl)
    return json.dumps(payload, ensure_ascii=False)


def _execute(spl: str) -> dict:
    from umodel_assistant.auth_context import Principal
    from umodel_assistant.config import load_settings
    from umodel_assistant.dispatch import Assistant

    # A new Assistant each call: execute_sync closes the MySQL pool.
    return Assistant(load_settings()).execute_sync(spl, "data", Principal("data-agent", "local"))


def chat(base_url: str, api_key: str, model: str, messages: list[dict], tools: list[dict], timeout: float = 60) -> dict:
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.2,
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise RuntimeError(f"model gateway HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"model gateway unreachable: {exc.reason}") from exc
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("model gateway returned no message") from exc
    if not isinstance(message, dict):
        raise RuntimeError("model gateway message was not an object")
    return message


def run(goal: str, complete_fn: Complete, query_fn: Query, max_steps: int = MAX_STEPS) -> str:
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": goal},
    ]
    for _ in range(max_steps):
        message = complete_fn(messages, TOOLS)
        calls = _tool_calls(message)
        assistant = {"role": "assistant", "content": message.get("content") or ""}
        if calls:
            assistant["tool_calls"] = calls
        messages.append(assistant)
        if not calls:
            text = (message.get("content") or "").strip()
            return text or "模型没有给出文字结论。"
        for call in calls:
            name = call["function"]["name"]
            if name != "query_umodel":
                content = json.dumps({"ok": False, "error": f"没有工具 {name}"}, ensure_ascii=False)
            else:
                content = query_fn(_spl_argument(call))
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "name": name or "query_umodel", "content": content}
            )
    return f"已经查了 {max_steps} 轮，停止。没有返回的内容不能当成结论。"


def _tool_calls(message: dict) -> list[dict]:
    calls: list[dict] = []
    raw_calls = message.get("tool_calls") or []
    if not isinstance(raw_calls, list):
        return calls
    for index, call in enumerate(raw_calls):
        if not isinstance(call, dict):
            continue
        function = call.get("function") if isinstance(call.get("function"), dict) else {}
        arguments = function.get("arguments")
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments or {}, ensure_ascii=False)
        calls.append(
            {
                "id": str(call.get("id") or f"call-{index}"),
                "type": "function",
                "function": {"name": str(function.get("name") or ""), "arguments": arguments},
            }
        )
    return calls


def _spl_argument(call: dict) -> str:
    raw = call["function"]["arguments"]
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    return str(parsed.get("spl_query") or "")


def require_runtime_env() -> None:
    required = ("OPENAI_BASE_URL", "OPENAI_API_KEY", "RMS_READONLY_PASSWORD", "RMS_MYSQL_ENDPOINT")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit("缺少环境变量：" + ", ".join(missing))
    if os.environ.get("UMODEL_WORKSPACE") != "rms":
        raise SystemExit("UMODEL_WORKSPACE 必须是 rms")


def live(goal: str) -> str:
    base_url = os.environ["OPENAI_BASE_URL"]
    api_key = os.environ["OPENAI_API_KEY"]
    model = os.environ.get("DATA_AGENT_MODEL") or "qwen3.8-flash"
    step = 0

    def complete_fn(messages: list[dict], tools: list[dict]) -> dict:
        nonlocal step
        step += 1
        print(f"\n--- 第 {step} 轮 ---", file=sys.stderr)
        return chat(base_url, api_key, model, messages, tools)

    def query_fn(spl: str) -> str:
        print(f"[工具] {spl}", file=sys.stderr)
        text = query_umodel(spl)
        print(f"[结果] {text}", file=sys.stderr)
        return text

    return run(goal, complete_fn, query_fn)
