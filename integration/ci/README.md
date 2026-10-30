# CI/CD boundary

The repository-root GitHub Actions workflow owns unit and integration checks.
This directory remains the authoritative local integration gate.

The local pipeline verifies RMS tests, Connector tests and linting, package
build, UModel environment checks, container image builds, Compose startup, and
the end-to-end model-guided smoke test. Run it with:

```sh
./scripts/ci-local.sh
```

Set `KEEP_STACK=1` to leave the Compose services running after the pipeline.

Cloud CD is deliberately not configured yet. It requires an approved image
registry, target environment, deployment identity, and rollback policy; none
of these should be guessed or embedded in source control.
