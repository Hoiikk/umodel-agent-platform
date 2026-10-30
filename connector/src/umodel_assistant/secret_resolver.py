"""Resolve credential_ref at runtime. The model stores a name, never a password."""

from __future__ import annotations

import os

from .errors import NotConfigured


class SecretResolver:
    def __init__(self, provider: str = "env") -> None:
        self.provider = provider

    def resolve(self, secret_ref: str) -> str:
        ref = (secret_ref or "").strip()
        if not ref:
            raise NotConfigured("secret", ["credential_ref"])
        if self.provider == "vault":
            # ENTERPRISE_HOOK: construct a Vault client from VAULT_ADDR and VAULT_ROLE.
            # Read the value at ref and return it. Do not log the value.
            raise NotConfigured("vault", ["VAULT_ADDR", "VAULT_ROLE"])
        if self.provider == "kms":
            # ENTERPRISE_HOOK: call the company KMS with ref. Do not log the value.
            raise NotConfigured("kms", ["KMS_KEY_ID", "KMS_REGION"])
        name = ref.removeprefix("secret://")
        value = os.environ.get(name, "")
        if not value:
            raise NotConfigured("env secret", [name])
        return value
