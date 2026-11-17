"""Run the Data Agent from the command line."""

from __future__ import annotations

import sys

from data_agent.agent import DEFAULT_GOAL, live, load_local_env, require_runtime_env

LOOPS = ("run", "graph")


def parse_args(argv: list[str]) -> tuple[str, str]:
    args = list(argv)
    loop = "run"
    if args and args[0] == "--loop":
        if len(args) < 2 or args[1] not in LOOPS:
            raise SystemExit("用法: data-agent [--loop run|graph] 问题")
        loop = args[1]
        args = args[2:]
    goal = " ".join(args).strip() or DEFAULT_GOAL
    return loop, goal


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:] if argv is None else argv
    loop, goal = parse_args(args)
    load_local_env()
    require_runtime_env()
    print(live(goal, loop))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
