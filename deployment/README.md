# Cloud deployment skeleton

This folder is a Docker Compose deployment target for the immutable images
published by `.github/workflows/release.yml`. It is intentionally inert until a
repository administrator configures a protected GitHub Environment.

## One-time staging host preparation

1. Provision a Linux host with Docker Engine, Docker Compose v2, `curl`, and an
   SSH deployment user.
2. On that host, create the protected deployment directory, for example
   `/opt/umodel-agent-platform/deployment`.
3. Copy `.env.example` to `.env` **on the host**, replace every value with a
   strong secret, and never commit that file.
4. If the GHCR packages remain private, authenticate the host with a token that
   has `read:packages` access before the first deployment.

## GitHub Environment configuration

Create `staging` and `production` Environments in repository settings. For each
Environment, add these secrets:

- `DEPLOY_HOST` — server hostname or IP address.
- `DEPLOY_USER` — SSH deployment user.
- `DEPLOY_PATH` — absolute deployment root, such as `/opt/umodel-agent-platform`.
- `DEPLOY_SSH_KEY` — private key for the deployment user.
- `DEPLOY_KNOWN_HOSTS` — pinned server host key line from `known_hosts`.

Set repository variable `CD_ENABLED` to `true` only after those secrets and the
server `.env` are ready. Keep it unset during configuration: the deploy job will
be skipped. Require reviewer approval for `production` and limit it to the
release process.

## Release and deploy

1. Create a release tag, such as `v0.1.0`, or manually run **Publish release
   images** with that version. The output includes `sha-*` tags.
2. Run **Deploy platform**, select `staging`, and use the exact `sha-*` tag.
3. After validation, run the same immutable tag against `production`, typing
   `DEPLOY` in the confirmation field. GitHub Environment approval is still
   required when configured.

The deploy workflow uploads only public deployment definition and semantic model
files. Database passwords remain on the server in `deployment/.env`.
