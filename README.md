# UModel Agent Platform

An enterprise-style local integration of a recruitment system, Alibaba
UnifiedModel, and a policy-enforced data connector for agents.

## Repository layout

- `rms/` — recruitment management system and its MySQL schema.
- `connector/` — model-guided, read-only data-fetch executor and MCP server.
- `integration/` — Compose environment, semantic model pack, smoke test, and local CI gate.
- `third_party/UnifiedModel` — pinned upstream UModel Git submodule; never modify it for product code.

## Start locally

```sh
cp rms/.env.example rms/.env
docker compose --env-file rms/.env -f integration/compose.yaml up --build
integration/scripts/run-smoke.sh
```

## Full local CI gate

```sh
integration/scripts/ci-local.sh
```

It runs RMS and Connector verification, package builds, UModel environment
checks, image builds, and the full UModel → Connector → MySQL smoke test.
