import json
import os

from data_agent.agent import TOOLS, apply_env_file, chat, query_umodel, run

SPL = ".entity_set with(domain='rms', name='rms.candidate', ids=['cand-004'])"


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

    payload = json.loads(query_umodel(".entity_set with(domain='rms', name='rms.candidate') | count", fail))
    assert payload == {"ok": False, "error": "只接受带一个 ids 的 rms.candidate 查询"}


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


def test_unknown_tool_is_rejected_and_step_limit_stops():
    def complete(messages, tools):
        return {"tool_calls": [{"id": "1", "function": {"name": "drop_table", "arguments": "{}"}}]}

    def query(spl: str) -> str:
        raise AssertionError(spl)

    text = run("删掉数据", complete, query, max_steps=2)
    assert text == "已经查了 2 轮，停止。没有返回的内容不能当成结论。"


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
