"""Run the Data Agent from the command line."""

from __future__ import annotations

import sys

from data_agent.agent import DEFAULT_GOAL, live, load_local_env, require_runtime_env


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    load_local_env()
    require_runtime_env()
    args = sys.argv[1:] if argv is None else argv
    goal = " ".join(args).strip() or DEFAULT_GOAL
    print(live(goal))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
