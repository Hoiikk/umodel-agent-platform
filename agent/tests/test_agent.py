import json
import os

from data_agent.agent import TOOLS, apply_env_file, chat, query_umodel, run

SPL = ".entity_set with(domain='rms', name='rms.candidate', ids=['cand-004'])"
STATUS_SPL = ".entity_set with(domain='rms', name='rms.candidate', status='HIRED')"
OPENING_SPL = ".entity_set with(domain='rms', name='rms.opening', ids=['job-001'])"
_REJECT = "只接受 rms.candidate 的一个编号、一个状态、一个职位或一个所属编制，或 rms.opening 的一个编号"


def test_env_file_does_not_override(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "already")
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY=from-file\nRMS_MYSQL_ENDPOINT=127.0.0.1:3308\n# comment\n\n", encoding="utf-8")
    apply_env_file(path)
    assert os.environ["OPENAI_API_KEY"] == "already"
    assert os.environ["RMS_MYSQL_ENDPOINT"] == "127.0.0.1:3308"


def test_query_rejects_unsupported_spl_without_calling_storage():
    def fail(spl: str) -> dict:
        raise AssertionError(spl)

    samples = [
        ".entity_set with(domain='rms', name='rms.candidate') | count",
        ".entity_set with(domain='rms', name='rms.candidate', source='猎聘')",
        ".entity_set with(domain='commerce', name='commerce.order', ids=['U-1001'])",
        ".topo | limit 20",
    ]
    for sample in samples:
        payload = json.loads(query_umodel(sample, fail))
        assert payload == {"ok": False, "error": _REJECT}
    opening_filter = ".entity_set with(domain='rms', name='rms.opening', title='前端工程师')"
    assert json.loads(query_umodel(opening_filter, fail)) == {"ok": False, "error": _REJECT}


def test_opening_query_calls_storage():
    seen = []

    def execute(spl: str) -> dict:
        seen.append(spl)
        return {"ok": True, "data": [{"opening_id": "job-001", "title": "前端工程师", "headcount": 2}]}

    payload = json.loads(query_umodel(OPENING_SPL, execute))
    assert seen == [OPENING_SPL]
    assert payload["data"][0]["headcount"] == 2


def test_status_query_calls_storage():
    seen = []

    def execute(spl: str) -> dict:
        seen.append(spl)
        return {"ok": True, "data": [{"candidate_id": "cand-005", "status": "HIRED"}]}

    payload = json.loads(query_umodel(STATUS_SPL, execute))
    assert seen == [STATUS_SPL]
    assert payload["data"][0]["candidate_id"] == "cand-005"


def test_query_calls_storage_for_one_id():
    seen = []

    def execute(spl: str) -> dict:
        seen.append(spl)
        return {"ok": True, "data": [{"candidate_id": "cand-004", "status": "INTERVIEWING"}]}

    payload = json.loads(query_umodel(SPL, execute))
    assert seen == [SPL]
    assert payload["data"][0]["status"] == "INTERVIEWING"


def test_loop_stops_when_the_model_answers():
    replies = [
        {
            "tool_calls": [
                {"id": "1", "function": {"name": "query_umodel", "arguments": json.dumps({"spl_query": SPL})}}
            ]
        },
        {"content": "cand-004 当前是面试中。"},
    ]

    def complete(messages, tools):
        assert tools[0]["function"]["name"] == "query_umodel"
        return replies.pop(0)

    seen = []
    text = run("cand-004 现在什么状态", complete, lambda spl: seen.append(spl) or '{"ok": true, "data": []}')
    assert seen == [SPL]
    assert text == "cand-004 当前是面试中。"


def test_several_lookups_in_one_turn_count_as_one_step():
    calls = [
        {
            "id": str(i),
            "function": {
                "name": "query_umodel",
                "arguments": json.dumps({"spl_query": SPL.replace("cand-004", f"cand-00{i}")}),
            },
        }
        for i in range(1, 9)
    ]
    replies = [{"tool_calls": calls}, {"content": "八个人都查到了。"}]

    def complete(messages, tools):
        return replies.pop(0)

    seen = []
    text = run(
        "分别告诉我 cand-001 到 cand-008 的状态",
        complete,
        lambda spl: seen.append(spl) or '{"ok": true, "data": []}',
        max_steps=2,
    )
    assert len(seen) == 8
    assert text == "八个人都查到了。"


def test_unknown_tool_is_rejected_and_step_limit_stops():
    def complete(messages, tools):
        return {"tool_calls": [{"id": "1", "function": {"name": "drop_table", "arguments": "{}"}}]}

    def query(spl: str) -> str:
        raise AssertionError(spl)

    text = run("删掉数据", complete, query, max_steps=2)
    assert text == "已经查了 2 轮，停止。没有返回的内容不能当成结论。"


def _tool(call_id: str, spl: str) -> dict:
    return {"id": call_id, "function": {"name": "query_umodel", "arguments": json.dumps({"spl_query": spl})}}


def test_conclusion_waits_until_every_named_id_was_queried():
    spl_004 = SPL
    spl_005 = SPL.replace("cand-004", "cand-005")
    replies = [
        {"tool_calls": [_tool("1", spl_004)]},
        {"content": "cand-004 更靠后。"},
        {"tool_calls": [_tool("2", spl_005)]},
        {"content": "cand-005 已录用，更靠后。"},
    ]
    nudged = []

    def complete(messages, tools):
        nudged.extend(item["content"] for item in messages if "还没查全" in item.get("content", ""))
        return replies.pop(0)

    seen = []
    text = run(
        "比较 cand-004 和 cand-005，谁更靠后",
        complete,
        lambda spl: seen.append(spl) or '{"ok": true, "data": []}',
    )
    assert seen == [spl_004, spl_005]
    assert text == "cand-005 已录用，更靠后。"
    assert any("cand-005" in item for item in nudged)


def test_a_short_range_includes_the_ids_in_between():
    spl_001 = SPL.replace("cand-004", "cand-001")
    spl_002 = SPL.replace("cand-004", "cand-002")
    spl_003 = SPL.replace("cand-004", "cand-003")
    replies = [
        {"tool_calls": [_tool("1", spl_001), _tool("2", spl_003)]},
        {"content": "两端就够了。"},
        {"tool_calls": [_tool("3", spl_002)]},
        {"content": "三个人都查过了。"},
    ]

    def complete(messages, tools):
        return replies.pop(0)

    seen = []
    text = run(
        "分别告诉我 cand-001 到 cand-003 的状态",
        complete,
        lambda spl: seen.append(spl) or '{"ok": true, "data": []}',
    )
    assert seen == [spl_001, spl_003, spl_002]
    assert text == "三个人都查过了。"


def test_a_wide_range_stays_the_two_written_ids():
    spl_001 = SPL.replace("cand-004", "cand-001")
    spl_030 = SPL.replace("cand-004", "cand-030")
    replies = [
        {"tool_calls": [_tool("1", spl_001), _tool("2", spl_030)]},
        {"content": "只查了写出来的两端。"},
    ]

    def complete(messages, tools):
        return replies.pop(0)

    text = run("看一下 cand-001 到 cand-030", complete, lambda spl: '{"ok": true, "data": []}')
    assert text == "只查了写出来的两端。"


def test_illegal_lookup_does_not_cover_a_named_id():
    bad = ".entity_set with(domain='rms', name='rms.candidate', ids=['cand-004']) | count"
    replies = [
        {"tool_calls": [_tool("1", bad)]},
        {"content": "cand-004 是面试中。"},
        {"tool_calls": [_tool("2", SPL)]},
        {"content": "cand-004 当前是面试中。"},
    ]

    def complete(messages, tools):
        return replies.pop(0)

    seen = []
    text = run("查询 cand-004", complete, lambda spl: seen.append(spl) or '{"ok": false}')
    assert seen == [bad, SPL]
    assert text == "cand-004 当前是面试中。"


def test_uncovered_ids_do_not_become_the_conclusion_when_steps_run_out():
    def complete(messages, tools):
        return {"content": "cand-004 已经录用。"}

    text = run("查询 cand-004", complete, lambda spl: "unused", max_steps=1)
    assert text == "已经查了 1 轮，停止。没有返回的内容不能当成结论。"


def test_question_without_ids_can_answer_without_a_lookup():
    def complete(messages, tools):
        return {"content": "没有对应的查询。"}

    def query(spl: str) -> str:
        raise AssertionError(spl)

    assert run("现在总共几个 cand", complete, query) == "没有对应的查询。"


def _rows_for(spl: str) -> str:
    if "rms.opening" in spl and "job-001" in spl:
        row = {"opening_id": "job-001", "title": "前端工程师", "headcount": 2}
        return json.dumps({"ok": True, "data": [row]}, ensure_ascii=False)
    if "cand-007" in spl:
        row = {"candidate_id": "cand-007", "position": "前端工程师", "status": "HIRED", "opening_id": "job-001"}
        return json.dumps({"ok": True, "data": [row]}, ensure_ascii=False)
    return '{"ok": true, "data": []}'


def test_opening_title_must_be_used_for_the_candidate_lookup():
    position = ".entity_set with(domain='rms', name='rms.candidate', position='前端工程师')"
    replies = [
        {"tool_calls": [_tool("1", OPENING_SPL)]},
        {"content": "有三个前端。"},
        {"tool_calls": [_tool("2", position)]},
        {"content": "三个人都查过了。"},
    ]
    nudged = []

    def complete(messages, tools):
        nudged.extend(item["content"] for item in messages if "编制返回的职位" in item.get("content", ""))
        return replies.pop(0)

    seen = []
    text = run(
        "job-001 这个编制对应的职位，现在有哪些候选人",
        complete,
        lambda spl: seen.append(spl) or _rows_for(spl),
    )
    assert seen == [OPENING_SPL, position]
    assert text == "三个人都查过了。"
    assert any("前端工程师" in item for item in nudged)


def test_same_turn_position_guess_does_not_count():
    position = ".entity_set with(domain='rms', name='rms.candidate', position='前端工程师')"
    replies = [
        {"tool_calls": [_tool("1", OPENING_SPL), _tool("2", position)]},
        {"content": "已经一起查了。"},
        {"tool_calls": [_tool("3", position)]},
        {"content": "看到职位后再查了。"},
    ]

    def complete(messages, tools):
        return replies.pop(0)

    seen = []
    text = run("job-001 这个编制有哪些候选人", complete, lambda spl: seen.append(spl) or _rows_for(spl))
    assert seen == [OPENING_SPL, position, position]
    assert text == "看到职位后再查了。"


def test_wrong_position_does_not_finish_the_followup():
    wrong = ".entity_set with(domain='rms', name='rms.candidate', position='后端工程师')"
    right = ".entity_set with(domain='rms', name='rms.candidate', position='前端工程师')"
    replies = [
        {"tool_calls": [_tool("1", OPENING_SPL)]},
        {"tool_calls": [_tool("2", wrong)]},
        {"content": "后端的人。"},
        {"tool_calls": [_tool("3", right)]},
        {"content": "前端的人。"},
    ]

    def complete(messages, tools):
        return replies.pop(0)

    seen = []
    text = run("job-001 这个编制有哪些候选人", complete, lambda spl: seen.append(spl) or _rows_for(spl))
    assert seen == [OPENING_SPL, wrong, right]
    assert text == "前端的人。"


def test_empty_opening_does_not_require_a_candidate_lookup():
    opening = OPENING_SPL.replace("job-001", "job-999")
    replies = [
        {"tool_calls": [_tool("1", opening)]},
        {"content": "没有这个编制。"},
    ]

    def complete(messages, tools):
        return replies.pop(0)

    seen = []
    text = run("查一下 job-999 这个编制有哪些候选人", complete, lambda spl: seen.append(spl) or _rows_for(spl))
    assert seen == [opening]
    assert text == "没有这个编制。"


def test_headcount_question_does_not_require_a_candidate_lookup():
    replies = [
        {"tool_calls": [_tool("1", OPENING_SPL)]},
        {"content": "前端工程师，编制人数 2。"},
    ]

    def complete(messages, tools):
        return replies.pop(0)

    text = run("job-001 这个职位编制要招几个人", complete, _rows_for)
    assert text == "前端工程师，编制人数 2。"


def test_headcount_uses_the_opening_id_from_the_candidate():
    candidate = SPL.replace("cand-004", "cand-007")
    replies = [
        {"tool_calls": [_tool("1", candidate)]},
        {"content": "还要招 2 人。"},
        {"tool_calls": [_tool("2", OPENING_SPL)]},
        {"content": "编制人数是 2。"},
    ]
    nudged = []

    def complete(messages, tools):
        nudged.extend(item["content"] for item in messages if "候选人返回的编制编号" in item.get("content", ""))
        return replies.pop(0)

    seen = []
    text = run(
        "cand-007 的编制人数是多少",
        complete,
        lambda spl: seen.append(spl) or _rows_for(spl),
    )
    assert seen == [candidate, OPENING_SPL]
    assert text == "编制人数是 2。"
    assert any("job-001" in item for item in nudged)


def test_same_turn_opening_guess_does_not_count():
    candidate = SPL.replace("cand-004", "cand-007")
    replies = [
        {"tool_calls": [_tool("1", candidate), _tool("2", OPENING_SPL)]},
        {"content": "已经一起查了。"},
        {"tool_calls": [_tool("3", OPENING_SPL)]},
        {"content": "看到编号后再查了。"},
    ]

    def complete(messages, tools):
        return replies.pop(0)

    seen = []
    text = run("cand-007 的编制人数是多少", complete, lambda spl: seen.append(spl) or _rows_for(spl))
    assert seen == [candidate, OPENING_SPL, OPENING_SPL]
    assert text == "看到编号后再查了。"


def test_which_opening_does_not_require_a_second_lookup():
    candidate = SPL.replace("cand-004", "cand-007")
    replies = [
        {"tool_calls": [_tool("1", candidate)]},
        {"content": "属于 job-001。"},
    ]

    def complete(messages, tools):
        return replies.pop(0)

    text = run("cand-007 属于哪个编制", complete, _rows_for)
    assert text == "属于 job-001。"


def test_wrong_opening_does_not_finish_the_headcount_followup():
    candidate = SPL.replace("cand-004", "cand-007")
    wrong = OPENING_SPL.replace("job-001", "job-002")
    replies = [
        {"tool_calls": [_tool("1", candidate)]},
        {"tool_calls": [_tool("2", wrong)]},
        {"content": "后端的编制。"},
        {"tool_calls": [_tool("3", OPENING_SPL)]},
        {"content": "编制人数是 2。"},
    ]

    def complete(messages, tools):
        return replies.pop(0)

    seen = []
    text = run("cand-007 的编制人数是多少", complete, lambda spl: seen.append(spl) or _rows_for(spl))
    assert seen == [candidate, wrong, OPENING_SPL]
    assert text == "编制人数是 2。"


def test_opening_id_query_calls_storage():
    listed = ".entity_set with(domain='rms', name='rms.candidate', opening_id='job-001')"
    seen = []

    def execute(spl: str) -> dict:
        seen.append(spl)
        return {"ok": True, "data": [{"candidate_id": "cand-007", "status": "HIRED", "opening_id": "job-001"}]}

    payload = json.loads(query_umodel(listed, execute))
    assert seen == [listed]
    assert payload["data"][0]["status"] == "HIRED"


def test_remaining_seats_require_candidates_on_that_opening():
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
    text = run(
        "cand-007 这个人的编制还要招几个人",
        complete,
        lambda spl: seen.append(spl) or _rows_for(spl),
    )
    assert seen == [candidate, OPENING_SPL, listed]
    assert text == "计划 2，已录用 1，还剩 1。"
    assert any("job-001" in item for item in nudged)


def test_same_turn_opening_id_guess_does_not_count():
    candidate = SPL.replace("cand-004", "cand-007")
    listed = ".entity_set with(domain='rms', name='rms.candidate', opening_id='job-001')"
    replies = [
        {"tool_calls": [_tool("1", candidate), _tool("2", listed)]},
        {"content": "已经一起查了。"},
        {"tool_calls": [_tool("3", OPENING_SPL)]},
        {"content": "编制查过了。"},
        {"tool_calls": [_tool("4", listed)]},
        {"content": "看到编号后再数了。"},
    ]

    def complete(messages, tools):
        return replies.pop(0)

    seen = []
    text = run("cand-007 还剩几个名额", complete, lambda spl: seen.append(spl) or _rows_for(spl), max_steps=6)
    assert seen == [candidate, listed, OPENING_SPL, listed]
    assert text == "看到编号后再数了。"


def test_wrong_opening_id_does_not_finish_the_seat_followup():
    candidate = SPL.replace("cand-004", "cand-007")
    listed = ".entity_set with(domain='rms', name='rms.candidate', opening_id='job-001')"
    wrong = listed.replace("job-001", "job-002")
    replies = [
        {"tool_calls": [_tool("1", candidate)]},
        {"tool_calls": [_tool("2", OPENING_SPL), _tool("3", wrong)]},
        {"content": "还剩 0。"},
        {"tool_calls": [_tool("4", listed)]},
        {"content": "还剩 1。"},
    ]

    def complete(messages, tools):
        return replies.pop(0)

    seen = []
    text = run("cand-007 还剩几个名额", complete, lambda spl: seen.append(spl) or _rows_for(spl))
    assert seen == [candidate, OPENING_SPL, wrong, listed]
    assert text == "还剩 1。"


def test_chat_timeout_is_a_gateway_error(monkeypatch):
    def urlopen(request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr("data_agent.agent.urllib.request.urlopen", urlopen)
    try:
        chat("https://example.test/v1/", "secret", "qwen3.8-flash", [{"role": "user", "content": "hi"}], TOOLS)
    except RuntimeError as exc:
        assert str(exc) == "model gateway timed out after 60s"
    else:
        raise AssertionError("expected RuntimeError")


def test_chat_posts_openai_payload(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()

    def urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode())
        captured["auth"] = request.get_header("Authorization")
        return Response()

    monkeypatch.setattr("data_agent.agent.urllib.request.urlopen", urlopen)
    message = chat("https://example.test/v1/", "secret", "qwen3.8-flash", [{"role": "user", "content": "hi"}], TOOLS)
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["body"]["model"] == "qwen3.8-flash"
    assert captured["body"]["stream"] is False
    assert captured["auth"] == "Bearer secret"
    assert message["content"] == "ok"
