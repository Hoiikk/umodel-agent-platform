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
_CANDIDATE = r"^\.entity_set with\(domain='rms', name='rms\.candidate', "
_OPENING = r"^\.entity_set with\(domain='rms', name='rms\.opening', "
_CANDIDATE_ID = re.compile(_CANDIDATE + r"ids=\['([A-Za-z0-9_-]+)'\]\)$")
_POSITION_SPL = re.compile(_CANDIDATE + "position='([\u4e00-\u9fffA-Za-z0-9]{1,32})'\\)$")
_BY_OPENING_SPL = re.compile(_CANDIDATE + r"opening_id='([A-Za-z0-9_-]+)'\)$")
_OPENING_SPL = re.compile(_OPENING + r"ids=\['([A-Za-z0-9_-]+)'\]\)$")
_SPL_PATTERNS = (
    _CANDIDATE_ID,
    re.compile(_CANDIDATE + r"status='(?:APPLIED|SCREENING|INTERVIEWING|HIRED|REJECTED)'\)$"),
    _POSITION_SPL,
    _BY_OPENING_SPL,
    _OPENING_SPL,
)
_SPL_HELP = (
    ".entity_set with(domain='rms', name='rms.candidate', ids=['cand-001'])；"
    "或把 ids 换成 status='HIRED'、position='前端工程师'、opening_id='job-001'；"
    "编制用 .entity_set with(domain='rms', name='rms.opening', ids=['job-001'])。"
    "一次只能填其中一种。"
)
_SPL_REJECT = "只接受 rms.candidate 的一个编号、一个状态、一个职位或一个所属编制，或 rms.opening 的一个编号"
_ID = re.compile(r"(?<![A-Za-z0-9_-])(?:cand|job)-[A-Za-z0-9_-]+")
_RANGE = re.compile(r"(cand|job)-(\d+)\s*到\s*(cand|job)-(\d+)")
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_umodel",
            "description": "按一个候选人编号、状态、职位或所属编制查询，或按一个编制编号查编制。SPL 必须是规定格式。",
            "parameters": {
                "type": "object",
                "properties": {"spl_query": {"type": "string", "description": _SPL_HELP}},
                "required": ["spl_query"],
            },
        },
    }
]
SYSTEM = """你是招聘数据助手。只能通过 query_umodel 查数据。
SPL 只能是下面五种之一，一次只能填一种：
.entity_set with(domain='rms', name='rms.candidate', ids=['某个编号'])
.entity_set with(domain='rms', name='rms.candidate', status='HIRED')
.entity_set with(domain='rms', name='rms.candidate', position='前端工程师')
.entity_set with(domain='rms', name='rms.candidate', opening_id='某个编制编号')
.entity_set with(domain='rms', name='rms.opening', ids=['某个编制编号'])
status 只能是 APPLIED、SCREENING、INTERVIEWING、HIRED、REJECTED。
候选人编号用 rms.candidate 的 ids。编制编号（job- 开头）用 rms.opening 的 ids。
没给编号、按状态或职位问候选人时，用 status 或 position。
候选人字段只有 candidate_id、name、phone、email、position、status、source、reject_reason、opening_id、created_at。
编制字段只有 opening_id、title、headcount。title 是职位名称，headcount 是编制人数。
status 的含义是 APPLIED 已投递、SCREENING 筛选中、INTERVIEWING 面试中、HIRED 已录用、REJECTED 已淘汰。
姓名、电话、邮箱已经打码。没有面试评价。
reject_reason 是淘汰原因。它是空值就写没有这项数据，不要根据状态编造原因。
opening_id 是这个人所属的编制编号，例如 job-001。不要根据职位名称编造编号。
问题在问编制人数时，用返回的 opening_id 再查一次编制。编制人数只写这次查到的 headcount。
问题在问还要招几个人或还剩几个名额时，再用同一个 opening_id 查一次候选人。
还剩名额等于这次的 headcount 减去这些行里 status 为 HIRED 的行数。
已投递、筛选中、面试中、已淘汰不算已招。只写这个差，不要把其他查询的行数算进去。
返回几行就写几行。ok 不是 true，或 data 为空，表示没查到。不要编造没有返回的人、编制或数字。
编制没查到就写没有这个编制，不要列出候选人。
问题在问这个编制有哪些候选人，而且结果里有职位名称时，用返回的 title 再查一次 position，只写这次查到的人。
职位名称必须和返回的 title 一致，不要自己猜。
没有查询全部候选人的语句，不要把几次查询的行数相加当成总人数。
前进顺序是已投递、筛选中、面试中、已录用。已淘汰不能和仍在流程中的人比先后。
问题里写明的每个编号都要先查过再写结论。写成 cand-001 到 cand-008 时，中间每个编号也要查。
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
        payload = {"ok": False, "error": _SPL_REJECT}
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
    except TimeoutError as exc:
        raise RuntimeError(f"model gateway timed out after {timeout:g}s") from exc
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("model gateway returned no message") from exc
    if not isinstance(message, dict):
        raise RuntimeError("model gateway message was not an object")
    return message


def _expand_range(match: re.Match[str]) -> list[str]:
    # ponytail: same prefix and digit width only; a gap over 20 stays the two written ids
    prefix, start, other, end = match.group(1), match.group(2), match.group(3), match.group(4)
    if prefix != other or len(start) != len(end):
        return []
    left, right = int(start), int(end)
    if left > right or right - left > 20:
        return []
    width = len(start)
    return [f"{prefix}-{number:0{width}d}" for number in range(left, right + 1)]


def _named_ids(goal: str) -> list[str]:
    def widen(match: re.Match[str]) -> str:
        values = _expand_range(match)
        return " ".join(values) if values else match.group(0)

    found: list[str] = []
    for match in _ID.finditer(_RANGE.sub(widen, goal or "")):
        if match.group(0) not in found:
            found.append(match.group(0))
    return found


def _opening_title(content: str) -> str:
    try:
        payload = json.loads(content or "")
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        return ""
    data = payload.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return ""
    title = data[0].get("title")
    if not isinstance(title, str):
        return ""
    title = title.strip()
    spl = f".entity_set with(domain='rms', name='rms.candidate', position='{title}')"
    return title if _POSITION_SPL.match(spl) else ""


def _missing_followup_titles(goal: str, messages: list[dict]) -> list[str]:
    # ponytail: only job id + 候选人; title must be copied from the opening row, not guessed
    named = _named_ids(goal)
    if "候选人" not in (goal or "") or not any(item.startswith("job-") for item in named):
        return []
    results = {
        str(message.get("tool_call_id")): message.get("content") or ""
        for message in messages
        if message.get("role") == "tool" and message.get("tool_call_id")
    }
    pending: list[str] = []
    for message in messages:
        if message.get("role") != "assistant":
            continue
        fresh: list[str] = []
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            function = call.get("function")
            if not isinstance(function, dict) or function.get("name") != "query_umodel":
                continue
            spl = _spl_argument(call).strip()
            position = _POSITION_SPL.match(spl)
            if position and position.group(1) in pending:
                pending.remove(position.group(1))
                continue
            if not _OPENING_SPL.match(spl):
                continue
            title = _opening_title(results.get(str(call.get("id")), ""))
            if title and title not in fresh:
                fresh.append(title)
        for title in fresh:
            if title not in pending:
                pending.append(title)
    return pending


def _candidate_opening_id(content: str) -> str:
    try:
        payload = json.loads(content or "")
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        return ""
    data = payload.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return ""
    opening_id = data[0].get("opening_id")
    if not isinstance(opening_id, str):
        return ""
    opening_id = opening_id.strip()
    spl = f".entity_set with(domain='rms', name='rms.opening', ids=['{opening_id}'])"
    return opening_id if _OPENING_SPL.match(spl) else ""


def _missing_opening_followups(goal: str, messages: list[dict]) -> list[str]:
    # ponytail: only a cand id plus 招/人数; the opening id is copied from that row
    text = goal or ""
    if "招" not in text and "人数" not in text and "还剩" not in text and "剩余" not in text:
        return []
    if not any(item.startswith("cand-") for item in _named_ids(text)):
        return []
    results = {
        str(message.get("tool_call_id")): message.get("content") or ""
        for message in messages
        if message.get("role") == "tool" and message.get("tool_call_id")
    }
    pending: list[str] = []
    for message in messages:
        if message.get("role") != "assistant":
            continue
        fresh: list[str] = []
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            function = call.get("function")
            if not isinstance(function, dict) or function.get("name") != "query_umodel":
                continue
            spl = _spl_argument(call).strip()
            opening = _OPENING_SPL.match(spl)
            if opening and opening.group(1) in pending:
                pending.remove(opening.group(1))
                continue
            if not _CANDIDATE_ID.match(spl):
                continue
            opening_id = _candidate_opening_id(results.get(str(call.get("id")), ""))
            if opening_id and opening_id not in fresh:
                fresh.append(opening_id)
        for opening_id in fresh:
            if opening_id not in pending:
                pending.append(opening_id)
    return pending


def _missing_seat_followups(goal: str, messages: list[dict]) -> list[str]:
    # ponytail: 还要招/还剩 only; opening_id is copied from the candidate row, not guessed
    text = goal or ""
    if "还要招" not in text and "还剩" not in text and "剩余" not in text:
        return []
    if not any(item.startswith("cand-") for item in _named_ids(text)):
        return []
    results = {
        str(message.get("tool_call_id")): message.get("content") or ""
        for message in messages
        if message.get("role") == "tool" and message.get("tool_call_id")
    }
    pending: list[str] = []
    for message in messages:
        if message.get("role") != "assistant":
            continue
        fresh: list[str] = []
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            function = call.get("function")
            if not isinstance(function, dict) or function.get("name") != "query_umodel":
                continue
            spl = _spl_argument(call).strip()
            listed = _BY_OPENING_SPL.match(spl)
            if listed and listed.group(1) in pending:
                pending.remove(listed.group(1))
                continue
            if not _CANDIDATE_ID.match(spl):
                continue
            opening_id = _candidate_opening_id(results.get(str(call.get("id")), ""))
            if opening_id and opening_id not in fresh:
                fresh.append(opening_id)
        for opening_id in fresh:
            if opening_id not in pending:
                pending.append(opening_id)
    return pending


def _queried_ids(messages: list[dict]) -> set[str]:
    found: set[str] = set()
    for message in messages:
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            function = call.get("function")
            if not isinstance(function, dict) or function.get("name") != "query_umodel":
                continue
            spl = _spl_argument(call).strip()
            if not any(pattern.match(spl) for pattern in _SPL_PATTERNS):
                continue
            matched = re.search(r"ids=\['([^']+)'\]", spl)
            if matched:
                found.add(matched.group(1))
    return found


def run(goal: str, complete_fn: Complete, query_fn: Query, max_steps: int = MAX_STEPS) -> str:
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": goal},
    ]
    for _ in range(max_steps):
        message = complete_fn(messages, TOOLS)
        calls = _tool_calls(message)
        if not calls:
            missing = [item for item in _named_ids(goal) if item not in _queried_ids(messages)]
            if missing:
                note = "还没查全，缺 " + "、".join(missing) + "。先调用 query_umodel 查这些编号，再写结论。"
                print("[检查] " + note, file=sys.stderr)
                messages.append({"role": "user", "content": note})
                continue
            titles = _missing_followup_titles(goal, messages)
            if titles:
                quoted = "、".join(f"「{title}」" for title in titles)
                note = "还要用编制返回的职位" + quoted + "按 position 再查一次候选人。"
                print("[检查] " + note, file=sys.stderr)
                messages.append({"role": "user", "content": note})
                continue
            openings = _missing_opening_followups(goal, messages)
            if openings:
                note = "还要用候选人返回的编制编号 " + "、".join(openings) + " 再查一次编制。"
                print("[检查] " + note, file=sys.stderr)
                messages.append({"role": "user", "content": note})
                continue
            seats = _missing_seat_followups(goal, messages)
            if seats:
                note = "还要用编制编号 " + "、".join(seats) + " 按 opening_id 再查一次这个编制下的候选人。"
                print("[检查] " + note, file=sys.stderr)
                messages.append({"role": "user", "content": note})
                continue
            text = (message.get("content") or "").strip()
            return text or "模型没有给出文字结论。"
        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": calls})
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
