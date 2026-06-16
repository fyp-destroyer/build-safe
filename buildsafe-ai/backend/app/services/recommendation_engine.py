from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

TIME_ESTIMATES: dict[str, str] = {
    "electrical": "1-3 hours for inspection or minor fixture work",
    "plumbing": "1-4 hours depending on access and shutoff",
    "masonry_demolition": "Half day to 2 days depending on surface and debris handling",
    "painting": "2-8 hours per room plus drying time",
    "carpentry": "1-4 hours depending on mounting and alignment",
    "roofing": "Professional assessment required before estimating",
    "gas": "Licensed technician assessment required",
    "structural": "Engineer or contractor assessment required",
    "general": "30 minutes to 2 hours",
}

COST_ESTIMATES: dict[str, str] = {
    "electrical": "$50-$250 DIY materials, professional labor varies by scope",
    "plumbing": "$20-$180 DIY materials, more if hidden leaks are involved",
    "masonry_demolition": "$40-$500+ depending on tools, disposal, and permits",
    "painting": "$30-$250 depending on paint, primer, and room size",
    "carpentry": "$20-$200 depending on hardware and materials",
    "roofing": "Professional quote recommended",
    "gas": "Licensed professional quote required",
    "structural": "Engineer or contractor quote required",
    "general": "$10-$100",
}


def _load_json(filename: str) -> dict[str, Any]:
    with (DATA_DIR / filename).open("r", encoding="utf-8") as file:
        return json.load(file)


def get_recommendations(category_key: str, risk_level: str) -> dict[str, Any]:
    tools = _load_json("tools.json")
    materials = _load_json("materials.json")
    professionals = _load_json("professionals.json")

    category_tools = tools.get(category_key, tools["general"])
    material_payload = materials.get(category_key, materials["general"])
    professional_payload = professionals.get(category_key, professionals["general"])

    if risk_level in {"Safe DIY", "DIY with supervision"}:
        professional = professional_payload.get("optional", professional_payload["category"])
    else:
        professional = professional_payload["category"]

    return {
        "required_tools": category_tools,
        "required_materials": material_payload["materials"],
        "required_ppe": material_payload["ppe"],
        "estimated_time": TIME_ESTIMATES.get(category_key, TIME_ESTIMATES["general"]),
        "estimated_cost_range": COST_ESTIMATES.get(category_key, COST_ESTIMATES["general"]),
        "recommended_professional_category": professional,
    }
