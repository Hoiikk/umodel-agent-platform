"""Load the on-disk model pack and follow entity_set → data_link → storage_link."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import AssistantError


class ModelPack:
    def __init__(self, root: Path) -> None:
        self.elements: list[dict[str, Any]] = []
        for path in sorted(root.rglob("*.yaml")):
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and loaded.get("kind"):
                self.elements.append(loaded)

    def entity_names(self) -> set[str]:
        return {str(_meta(item)["name"]) for item in self.elements if item.get("kind") == "entity_set"}

    def event_fields(self) -> dict[str, frozenset[str]]:
        found: dict[str, frozenset[str]] = {}
        for item in self.elements:
            if item.get("kind") != "event_set":
                continue
            fields = item.get("spec", {}).get("fields") or []
            found[str(_meta(item)["name"])] = frozenset(
                str(field.get("name")) for field in fields if isinstance(field, dict)
            )
        return found

    def field_tags(self, event_name: str) -> dict[str, str]:
        for item in self.elements:
            if item.get("kind") == "event_set" and _meta(item).get("name") == event_name:
                tags: dict[str, str] = {}
                for field in item.get("spec", {}).get("fields") or []:
                    if not isinstance(field, dict):
                        continue
                    raw = field.get("tags") if isinstance(field.get("tags"), dict) else {}
                    tag = str(raw.get("classification") or "")
                    if tag:
                        tags[str(field.get("name"))] = tag
                return tags
        return {}

    def binding(self, domain: str, entity_name: str) -> dict[str, Any]:
        data_links = [
            item
            for item in self.elements
            if item.get("kind") == "data_link" and _ref(item, "src") == (domain, "entity_set", entity_name)
        ]
        own = [
            item
            for item in data_links
            if (dest := _endpoint(item, "dest")[2]) == entity_name or dest.startswith(entity_name + ".")
        ]
        chosen = own or data_links
        if len(chosen) != 1:
            raise AssistantError("model_link", f"{entity_name} must have exactly one data_link, found {len(chosen)}")
        data_link = chosen[0]
        dest_domain, dest_kind, dest_name = _endpoint(data_link, "dest")
        storage_links = [
            item
            for item in self.elements
            if item.get("kind") == "storage_link" and _ref(item, "src") == (dest_domain, dest_kind, dest_name)
        ]
        if len(storage_links) != 1:
            raise AssistantError(
                "ambiguous_storage",
                f"{dest_name} must have exactly one storage_link, found {len(storage_links)}",
            )
        storage_domain, storage_kind, storage_name = _endpoint(storage_links[0], "dest")
        return {
            "entity": _find(self.elements, "entity_set", domain, entity_name),
            "event": _find(self.elements, dest_kind, dest_domain, dest_name),
            "storage": _find(self.elements, storage_kind, storage_domain, storage_name),
            "storage_link": storage_links[0],
            "data_link": data_link,
        }


def _meta(item: dict[str, Any]) -> dict[str, Any]:
    meta = item.get("metadata")
    return meta if isinstance(meta, dict) else {}


def _endpoint(item: dict[str, Any], side: str) -> tuple[str, str, str]:
    spec = item.get("spec") if isinstance(item.get("spec"), dict) else {}
    ref = spec.get(side) if isinstance(spec.get(side), dict) else {}
    return str(ref.get("domain") or ""), str(ref.get("kind") or ""), str(ref.get("name") or "")


def _ref(item: dict[str, Any], side: str) -> tuple[str, str, str]:
    return _endpoint(item, side)


def _find(elements: list[dict[str, Any]], kind: str, domain: str, name: str) -> dict[str, Any]:
    for item in elements:
        meta = _meta(item)
        if item.get("kind") == kind and meta.get("domain") == domain and meta.get("name") == name:
            return item
    raise AssistantError("model_missing", f"missing {kind} {domain}/{name}")
