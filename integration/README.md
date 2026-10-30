# UModel RMS Integration Lab

This directory owns the local, cross-repository integration environment for:

- `../third_party/UnifiedModel`: the pinned upstream UModel semantic runtime;
- `../rms`: the recruitment management system; and
- `../connector`: the model-guided data-fetch executor.

It intentionally contains no business implementation. Future phases will add
Docker Compose definitions, deterministic fixtures, cross-service contract
tests, deployment scripts, and architecture decision records here so that the
three projects remain independently buildable.

## Local prerequisites

- Docker Desktop with Docker Compose v2;
- Go 1.22 or newer for UModel;
- Node.js and npm for RMS; and
- Python 3.10 or newer for the assistant.

## Safety boundary

No real business-system credentials, production data, or public deployment
configuration belong in this directory. The local integration environment will
use seeded data and least-privilege service accounts only.

## First integrated environment

Copy `../rms/.env.example` to `../rms/.env`, set unique local-only
passwords, then run `docker compose --env-file ../rms/.env up --build`.
This starts MySQL, RMS on
port 3001, and UModel on port 8080. Verify the service and import the mounted
RMS model pack with the upstream CLI:

```sh
cd ../third_party/UnifiedModel
go run ./cmd/umctl --addr http://127.0.0.1:8080 health
go run ./cmd/umctl --addr http://127.0.0.1:8080 workspace create rms
go run ./cmd/umctl --addr http://127.0.0.1:8080 umodel import rms --path /model-packs/rms
go run ./cmd/umctl --addr http://127.0.0.1:8080 query run rms '.umodel | limit 10'
```

The UModel import root is confined to the read-only `/model-packs` mount; do
not point imports at arbitrary container paths. The Connector remains a
separate stdio MCP process by design.

## End-to-end smoke test

After the stack is running, execute:

```sh
./scripts/run-smoke.sh
```

The script is idempotent: it checks UModel health, creates/imports the `rms`
workspace when needed, then verifies a model-guided candidate lookup through
the Connector and MySQL. It asserts the read-only path returns one row and
that name, phone, and email remain masked. The Compose-only MySQL port is
bound to `127.0.0.1:3308`; the Connector selects it through
`RMS_MYSQL_ENDPOINT`, while the model keeps its local-development default.
