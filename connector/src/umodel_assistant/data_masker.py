"""Mask fields the model tags. Untagged values are left unchanged."""

from __future__ import annotations

import re


def mask_rows(rows: list[dict], field_tags: dict[str, str]) -> list[dict]:
    if not field_tags:
        return rows
    masked: list[dict] = []
    for row in rows:
        copy = dict(row)
        for field, tag in field_tags.items():
            if field not in copy or copy[field] is None:
                continue
            fn = _BY_TAG.get(tag)
            if fn is not None:
                copy[field] = fn(str(copy[field]))
        masked.append(copy)
    return masked


def _name(value: str) -> str:
    if not value:
        return value
    return value[0] + ("*" * (len(value) - 1))


def _phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 7:
        return "***"
    return f"{digits[:3]}****{digits[-4:]}"


def _email(value: str) -> str:
    if "@" not in value:
        return "***"
    local, domain = value.split("@", 1)
    return f"{local[:1]}***@{domain}"


def _id_card(value: str) -> str:
    if len(value) < 8:
        return "***"
    return f"{value[:3]}***********{value[-4:]}"


_BY_TAG = {
    "pii.name": _name,
    "pii.phone": _phone,
    "pii.email": _email,
    "pii.id_card": _id_card,
}
