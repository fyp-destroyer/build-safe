from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _load_json(filename: str) -> Any:
    with (DATA_DIR / filename).open("r", encoding="utf-8") as file:
        return json.load(file)


def get_seed_data() -> dict[str, Any]:
    # TODO: PostgreSQL migration.
    # Move these JSON seed files into relational tables for categories, rules,
    # tool/material catalogs, PPE checklists, and professional category mappings.
    return {
        "tools": _load_json("tools.json"),
        "materials": _load_json("materials.json"),
        "safety_rules": _load_json("safety_rules.json")["rules"],
        "professional_categories": _load_json("professionals.json"),
    }
