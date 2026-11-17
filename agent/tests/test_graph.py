import json

from data_agent.graph import graph_run

SPL = ".entity_set with(domain='rms', name='rms.candidate', ids=['cand-004'])"
OPENING_SPL = ".entity_set with(domain='rms', name='rms.opening', ids=['job-001'])"


def _tool(call_id: str, spl: str) -> dict:
    return {"id": call_id, "function": {"name": "query_umodel", "arguments": json.dumps({"spl_query": spl})}}


def _rows_for(spl: str) -> str:
    if "rms.opening" in spl and "job-001" in spl:
        row = {"opening_id": "job-001", "title": "前端工程师", "headcount": 2}
        return json.dumps({"ok": True, "data": [row]}, ensure_ascii=False)
    if "cand-007" in spl:
        row = {"candidate_id": "cand-007", "position": "前端工程师", "status": "HIRED", "opening_id": "job-001"}
        return json.dumps({"ok": True, "data": [row]}, ensure_ascii=False)
    return '{"ok": true, "data": []}'


def test_graph_stops_when_the_model_answers():
    replies = [
        {"tool_calls": [_tool("1", SPL)]},
        {"content": "cand-004 当前是面试中。"},
    ]

    def complete(messages, tools):
        return replies.pop(0)

    seen = []
    text = graph_run("cand-004 现在什么状态", complete, lambda spl: seen.append(spl) or '{"ok": true, "data": []}')
    assert seen == [SPL]
    assert text == "cand-004 当前是面试中。"


def test_graph_waits_until_every_named_id_was_queried():
    spl_005 = SPL.replace("cand-004", "cand-005")
    replies = [
        {"tool_calls": [_tool("1", SPL)]},
        {"content": "cand-004 更靠后。"},
        {"tool_calls": [_tool("2", spl_005)]},
        {"content": "cand-005 已录用，更靠后。"},
    ]
    nudged = []

    def complete(messages, tools):
        nudged.extend(item["content"] for item in messages if "还没查全" in item.get("content", ""))
        return replies.pop(0)

    seen = []
    text = graph_run(
        "比较 cand-004 和 cand-005，谁更靠后",
        complete,
        lambda spl: seen.append(spl) or '{"ok": true, "data": []}',
    )
    assert seen == [SPL, spl_005]
    assert text == "cand-005 已录用，更靠后。"
    assert any("cand-005" in item for item in nudged)


def test_graph_rejects_an_unknown_tool_until_the_step_limit():
    def complete(messages, tools):
        return {"tool_calls": [{"id": "1", "function": {"name": "drop_table", "arguments": "{}"}}]}

    def query(spl: str) -> str:
        raise AssertionError(spl)

    text = graph_run("删掉数据", complete, query, max_steps=2)
    assert text == "已经查了 2 轮，停止。没有返回的内容不能当成结论。"


def test_graph_remaining_seats_require_candidates_on_that_opening():
    candidate = SPL.replace("cand-004", "cand-007")
    listed = ".entity_set with(domain='rms', name='rms.candidate', opening_id='job-001')"
    replies = [
        {"tool_calls": [_tool("1", candidate)]},
        {"tool_calls": [_tool("2", OPENING_SPL)]},
        {"content": "还剩 2 人。"},
        {"tool_calls": [_tool("3", listed)]},
        {"content": "计划 2，已录用 1，还剩 1。"},
    ]
    nudged = []

    def complete(messages, tools):
        nudged.extend(item["content"] for item in messages if "按 opening_id" in item.get("content", ""))
        return replies.pop(0)

    seen = []
    text = graph_run("cand-007 这个人的编制还要招几个人", complete, lambda spl: seen.append(spl) or _rows_for(spl))
    assert seen == [candidate, OPENING_SPL, listed]
    assert text == "计划 2，已录用 1，还剩 1。"
    assert any("job-001" in item for item in nudged)
