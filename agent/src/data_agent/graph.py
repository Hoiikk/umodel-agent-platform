"""The same loop as run(), selected with --loop graph."""

from __future__ import annotations

import json
import sys
from typing import TypedDict

from langgraph.graph import END, StateGraph

from data_agent.agent import MAX_STEPS, SYSTEM, TOOLS, Complete, Query, _spl_argument, _tool_calls, pending_note


class LoopState(TypedDict):
    messages: list[dict]
    goal: str
    steps: int
    max_steps: int
    draft: dict
    result: str


def graph_run(goal: str, complete_fn: Complete, query_fn: Query, max_steps: int = MAX_STEPS) -> str:
    def model(state: LoopState) -> dict:
        if state["steps"] >= state["max_steps"]:
            return {
                "result": f"已经查了 {state['max_steps']} 轮，停止。没有返回的内容不能当成结论。",
            }
        return {"steps": state["steps"] + 1, "draft": complete_fn(state["messages"], TOOLS), "result": ""}

    def tools(state: LoopState) -> dict:
        message = state["draft"]
        calls = _tool_calls(message)
        messages = list(state["messages"])
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
        return {"messages": messages}

    def check(state: LoopState) -> dict:
        note = pending_note(state["goal"], state["messages"])
        if note:
            print("[检查] " + note, file=sys.stderr)
            messages = list(state["messages"])
            messages.append({"role": "user", "content": note})
            return {"messages": messages, "result": ""}
        text = (state["draft"].get("content") or "").strip()
        return {"result": text or "模型没有给出文字结论。"}

    def after_model(state: LoopState) -> str:
        if state["result"]:
            return "end"
        if _tool_calls(state["draft"]):
            return "tools"
        return "check"

    def after_check(state: LoopState) -> str:
        return "end" if state["result"] else "model"

    graph = StateGraph(LoopState)
    graph.add_node("model", model)
    graph.add_node("tools", tools)
    graph.add_node("check", check)
    graph.set_entry_point("model")
    graph.add_conditional_edges("model", after_model, {"tools": "tools", "check": "check", "end": END})
    graph.add_edge("tools", "model")
    graph.add_conditional_edges("check", after_check, {"model": "model", "end": END})
    final = graph.compile().invoke(
        {
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": goal}],
            "goal": goal,
            "steps": 0,
            "max_steps": max_steps,
            "draft": {},
            "result": "",
        },
        {"recursion_limit": max_steps * 4 + 5},
    )
    return str(final.get("result") or "")
