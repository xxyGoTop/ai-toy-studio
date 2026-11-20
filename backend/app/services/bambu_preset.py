from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PROFILE_ROOT = Path(r"D:\BambuStudio\resources\profiles\BBL")
SKIP = {"type", "name", "inherits", "from", "instantiation", "description", "setting_id"}


def _index() -> dict[str, Path]:
    found: dict[str, Path] = {}
    if not PROFILE_ROOT.exists():
        return found
    for path in PROFILE_ROOT.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = payload.get("name")
        if isinstance(name, str) and name not in found:
            found[name] = path
    return found


@lru_cache
def resolve(name: str) -> dict:
    index = _index()
    path = index.get(name)
    if path is None:
        raise FileNotFoundError(name)
    payload = json.loads(path.read_text(encoding="utf-8"))
    merged: dict = {}
    parent = payload.get("inherits")
    if isinstance(parent, str) and parent:
        merged.update(resolve(parent))
    for include_name in payload.get("include") or []:
        if isinstance(include_name, str) and include_name in index:
            merged.update(resolve(include_name))
    for key, value in payload.items():
        if key in SKIP or key == "include":
            continue
        merged[key] = value
    merged["name"] = name
    return merged
