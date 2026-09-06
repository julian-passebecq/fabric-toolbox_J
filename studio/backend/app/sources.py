from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


STUDIO_DIR = Path(__file__).resolve().parents[2]
SOURCE_REGISTRY = STUDIO_DIR / "sources" / "source-registry.yaml"


def load_source_registry() -> dict[str, Any]:
    if not SOURCE_REGISTRY.exists():
        return {"schema_version": 1, "product": "Fabric Ops Studio", "sources": []}
    with SOURCE_REGISTRY.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("Source registry root must be a mapping")
    data.setdefault("sources", [])
    data.setdefault("excluded_from_product_surface", [])
    return data
