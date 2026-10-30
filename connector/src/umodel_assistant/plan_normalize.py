"""Turn Go execute responses into rows, a storage plan, or a structured error.

Go writes three envelopes. format=agent + include_spec puts a plan object at the
top level. The legacy envelope is {data: {header, data}}. responseType 1 stores
the plan JSON in the query column. responseType 2 is already rows (list_*).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Normalized:
    kind: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    plan: dict[str, Any] | None = None
    code: str = ""
    message: str = ""
    details: dict[str, str] = field(default_factory=dict)


def normalize(body: dict[str, Any]) -> Normalized:
    error = body.get("error")
    if isinstance(error, dict) and error.get("code"):
        details = error.get("details") if isinstance(error.get("details"), dict) else {}
        return Normalized(
            kind="error",
            code=str(error.get("code")),
            message=str(error.get("message") or ""),
            details={str(key): str(value) for key, value in details.items()},
        )
    if isinstance(body.get("query"), dict) and body.get("mode") == "plan":
        return Normalized(kind="plan", plan=body)
    header, matrix = _matrix(body)
    if header is None:
        return Normalized(kind="error", code="bad_envelope", message="unrecognized UModel execute response")
    rows = _zip(header, matrix)
    if len(rows) == 1 and str(rows[0].get("responseType")) == "1":
        return Normalized(kind="plan", plan=_parse_plan(rows[0].get("query")))
    if len(rows) == 1 and str(rows[0].get("responseType")) == "2":
        inner_header = rows[0].get("header") if isinstance(rows[0].get("header"), list) else []
        inner = rows[0].get("data") if isinstance(rows[0].get("data"), list) else []
        return Normalized(kind="rows", rows=_coerce_inner(inner_header, inner))
    return Normalized(kind="rows", rows=rows)


def _matrix(body: dict[str, Any]) -> tuple[list[Any] | None, list[Any]]:
    data = body.get("data")
    if isinstance(data, dict) and isinstance(data.get("header"), list):
        matrix = data.get("data")
        return data["header"], matrix if isinstance(matrix, list) else []
    if isinstance(body.get("header"), list) and isinstance(body.get("data"), list):
        return body["header"], body["data"]
    return None, []


def _zip(header: list[Any], matrix: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    names = [str(column) for column in header]
    for item in matrix:
        if isinstance(item, dict) and isinstance(item.get("values"), list):
            item = item["values"]
        if isinstance(item, list):
            rows.append({name: item[index] if index < len(item) else None for index, name in enumerate(names)})
    return rows


def _parse_plan(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    return {}


def _coerce_inner(header: list[Any], data: list[Any]) -> list[dict[str, Any]]:
    if data and isinstance(data[0], dict) and "values" not in data[0]:
        return [row for row in data if isinstance(row, dict)]
    return _zip(header, data)
