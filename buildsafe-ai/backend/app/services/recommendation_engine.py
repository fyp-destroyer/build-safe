from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.schemas import TaskIntent

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

TIME_ESTIMATES: dict[str, str] = {
    "electrical": "1-3 hours for inspection or minor fixture work",
    "plumbing": "1-4 hours depending on access and shutoff",
    "masonry_demolition": "Half day to 2 days depending on surface and debris handling",
    "tiling": "Half day to 2 days depending on layout, surface preparation, and curing time",
    "painting": "2-8 hours per room plus drying time",
    "carpentry": "1-4 hours depending on mounting and alignment",
    "hvac": "30 minutes for filter replacement; professional assessment for AC, refrigerant, or furnace work",
    "roofing": "Professional assessment required before estimating",
    "gas": "Licensed technician assessment required",
    "structural": "Engineer or contractor assessment required",
    "general": "30 minutes to 2 hours",
}

COST_ESTIMATES: dict[str, str] = {
    "electrical": "$50-$250 DIY materials, professional labor varies by scope",
    "plumbing": "$20-$180 DIY materials, more if hidden leaks are involved",
    "masonry_demolition": "$40-$500+ depending on tools, disposal, and permits",
    "tiling": "$50-$600+ depending on area, tile type, adhesive, grout, and waterproofing",
    "painting": "$30-$250 depending on paint, primer, and room size",
    "carpentry": "$20-$200 depending on hardware and materials",
    "hvac": "$10-$80 for filter/thermostat materials; professional quote for AC, duct, refrigerant, or furnace work",
    "roofing": "Professional quote recommended",
    "gas": "Licensed professional quote required",
    "structural": "Engineer or contractor quote required",
    "general": "$10-$100",
}

INTENT_RECOMMENDATIONS: dict[TaskIntent, dict[str, Any]] = {
    "hanging_wall_decor": {
        "required_tools": ["measuring tape", "level", "pencil", "hammer"],
        "required_materials": [
            "picture hooks",
            "screws",
            "wall plugs or anchors",
            "adhesive strips for lightweight frames",
            "hanging wire if needed",
        ],
        "required_ppe": ["safety glasses if drilling", "gloves optional"],
        "estimated_time": "15-60 minutes depending on wall type and artwork size",
        "estimated_cost_range": "$5-$60 depending on hooks, anchors, and fixing method",
        "recommended_professional_category": {
            "low_risk": "No professional usually required for standard wall decor; consider a handyman or carpenter if the item is heavy or the wall is tiled, concrete, or uncertain",
            "high_risk": "Handyman or carpenter recommended for heavy, high, tiled, concrete, or uncertain wall installations",
        },
    },
    "wall_painting": {
        "required_tools": ["paint roller", "brush set", "paint tray", "painter's tape", "drop cloth"],
        "required_materials": ["paint", "primer", "filler if needed", "sandpaper", "surface protection sheets"],
        "required_ppe": ["safety glasses", "nitrile gloves", "mask or respirator for low ventilation"],
        "estimated_time": "2-8 hours per room plus drying time between coats",
        "estimated_cost_range": "$30-$250 depending on paint system, primer, and room size",
        "recommended_professional_category": {
            "low_risk": "No professional usually required unless height, lead paint, or poor ventilation is involved",
            "high_risk": "Painter or handyman",
        },
    },
    "ceiling_fan_installation": {
        "required_tools": ["voltage tester", "insulated screwdriver", "drill", "stable ladder", "wire stripper"],
        "required_materials": ["fan-rated ceiling box", "mounting bracket", "wire connectors", "electrical tape"],
        "required_ppe": ["safety glasses", "insulated gloves", "non-conductive footwear"],
        "estimated_time": "1-3 hours depending on wiring, access, and support hardware",
        "estimated_cost_range": "$50-$250 DIY materials, professional labor varies by scope",
        "recommended_professional_category": {
            "low_risk": "Electrician recommended if you are not confident with wiring or fixture support checks",
            "high_risk": "Licensed electrician",
        },
    },
    "plumbing_leak_repair": {
        "required_tools": ["adjustable wrench", "pipe wrench", "bucket", "utility knife", "torch or work light"],
        "required_materials": ["plumber's tape", "replacement washer", "pipe joint compound", "absorbent cloths"],
        "required_ppe": ["waterproof gloves", "eye protection", "knee pads"],
        "estimated_time": "30 minutes to 4 hours depending on access, isolation, and leak severity",
        "estimated_cost_range": "$20-$180 depending on parts, access, and whether the line is exposed or hidden",
        "recommended_professional_category": {
            "low_risk": "No professional usually required for a minor accessible leak, but a plumber is recommended if the source is uncertain",
            "high_risk": "Licensed plumber",
        },
    },
    "wall_demolition": {
        "required_tools": ["stud finder", "hammer", "utility knife", "masonry drill", "dust collection bags"],
        "required_materials": ["dust sheets", "debris bags", "patching compound", "temporary protection materials"],
        "required_ppe": ["hard hat", "dust mask or respirator", "work gloves", "safety goggles", "hearing protection"],
        "estimated_time": "Half day to 2 days depending on structure checks, demolition method, and debris handling",
        "estimated_cost_range": "$40-$500+ depending on tools, disposal, permits, and structural review",
        "recommended_professional_category": {
            "low_risk": "Experienced contractor recommended before any wall removal",
            "high_risk": "Mason, demolition contractor, or structural engineer",
        },
    },
    "light_bulb_replacement": {
        "required_tools": ["stable step stool or ladder if needed", "clean cloth"],
        "required_materials": ["correct replacement bulb"],
        "required_ppe": ["gloves optional", "safety glasses if using overhead access"],
        "estimated_time": "5-20 minutes",
        "estimated_cost_range": "$5-$30 depending on bulb type",
        "recommended_professional_category": {
            "low_risk": "No professional usually required for a standard like-for-like bulb replacement",
            "high_risk": "Electrician recommended if the fitting or wiring is involved",
        },
    },
    "shelf_installation": {
        "required_tools": ["measuring tape", "level", "pencil", "drill", "stud finder", "screwdriver set"],
        "required_materials": ["shelf brackets", "screws", "wall anchors", "appropriate fixings for the wall type"],
        "required_ppe": ["safety glasses", "work gloves"],
        "estimated_time": "30-90 minutes depending on wall type and shelf load",
        "estimated_cost_range": "$15-$120 depending on fixings, brackets, and shelf size",
        "recommended_professional_category": {
            "low_risk": "Handyman optional for heavy shelves or uncertain wall types",
            "high_risk": "Carpenter or handyman",
        },
    },
    "tile_installation": {
        "required_tools": ["tile cutter", "notched trowel", "rubber float", "level", "spacers", "sponge"],
        "required_materials": ["tiles", "thinset or tile adhesive", "grout", "tile spacers", "silicone sealant"],
        "required_ppe": ["cut-resistant gloves", "safety goggles", "knee pads", "dust mask"],
        "estimated_time": "Half day to 2 days depending on layout, cutting, and curing",
        "estimated_cost_range": "$50-$600+ depending on tile type, area, and substrate preparation",
        "recommended_professional_category": {
            "low_risk": "Tile installer recommended for wet areas or large-format tile",
            "high_risk": "Tile installer or waterproofing contractor",
        },
    },
    "furniture_assembly": {
        "required_tools": ["screwdriver set", "hex keys", "rubber mallet", "measuring tape"],
        "required_materials": ["manufacturer hardware kit", "surface protection cloth"],
        "required_ppe": ["work gloves"],
        "estimated_time": "30 minutes to 3 hours depending on item size and complexity",
        "estimated_cost_range": "$0-$40 if only basic tools are needed",
        "recommended_professional_category": {
            "low_risk": "No professional usually required for standard furniture assembly",
            "high_risk": "Handyman or carpenter for large, heavy, or anchored items",
        },
    },
}

INTENT_CONSISTENCY_RULES: dict[TaskIntent, dict[str, Any]] = {
    "hanging_wall_decor": {
        "forbidden_tool_keywords": ("roller", "brush", "tray"),
        "forbidden_material_keywords": ("paint", "primer", "drop cloth"),
        "forbidden_time_keywords": ("drying",),
        "forbidden_professional_keywords": ("painter",),
        "forbidden_explanation_keywords": ("paint the room", "paint the wall", "repaint", "drying time"),
        "fallback_explanation": (
            "This task is being treated as hanging wall decor rather than painting the room. "
            "The main considerations are item weight, wall material, and whether drilling is needed."
        ),
    },
    "wall_painting": {
        "forbidden_tool_keywords": ("picture hook", "stud finder"),
        "forbidden_material_keywords": ("hanging wire", "adhesive strip"),
        "forbidden_time_keywords": (),
        "forbidden_professional_keywords": ("carpenter",),
        "forbidden_explanation_keywords": ("hang artwork", "wall decor"),
        "fallback_explanation": (
            "This task is being treated as applying paint to room surfaces, so preparation, "
            "ventilation, surface condition, and drying time are relevant."
        ),
    },
}


def _load_json(filename: str) -> dict[str, Any]:
    with (DATA_DIR / filename).open("r", encoding="utf-8") as file:
        return json.load(file)


def get_recommendations(
    category_key: str,
    risk_level: str,
    task_intent: TaskIntent,
) -> dict[str, Any]:
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

    intent_profile = INTENT_RECOMMENDATIONS.get(task_intent, {})
    professional_override = intent_profile.get("recommended_professional_category", {})
    if professional_override:
        professional = (
            professional_override.get("low_risk")
            if risk_level in {"Safe DIY", "DIY with supervision"}
            else professional_override.get("high_risk")
        ) or professional

    return {
        "required_tools": intent_profile.get("required_tools", category_tools),
        "required_materials": intent_profile.get("required_materials", material_payload["materials"]),
        "required_ppe": intent_profile.get("required_ppe", material_payload["ppe"]),
        "estimated_time": intent_profile.get(
            "estimated_time",
            TIME_ESTIMATES.get(category_key, TIME_ESTIMATES["general"]),
        ),
        "estimated_cost_range": intent_profile.get(
            "estimated_cost_range",
            COST_ESTIMATES.get(category_key, COST_ESTIMATES["general"]),
        ),
        "recommended_professional_category": professional,
    }


def validate_assessment_consistency(
    *,
    task_intent: TaskIntent,
    explanation: str,
    recommendations: dict[str, Any],
    selected_interpretation: str = "",
    risk_level: str = "Safe DIY",
) -> dict[str, Any]:
    cleaned = dict(recommendations)
    profile = INTENT_RECOMMENDATIONS.get(task_intent, {})
    rules = INTENT_CONSISTENCY_RULES.get(task_intent, {})
    contradictions: list[str] = []

    cleaned["required_tools"], tool_conflicts = _filter_conflicting_items(
        cleaned.get("required_tools", []),
        rules.get("forbidden_tool_keywords", ()),
    )
    cleaned["required_materials"], material_conflicts = _filter_conflicting_items(
        cleaned.get("required_materials", []),
        rules.get("forbidden_material_keywords", ()),
    )

    contradictions.extend([f"tools: {item}" for item in tool_conflicts])
    contradictions.extend([f"materials: {item}" for item in material_conflicts])

    if tool_conflicts and profile.get("required_tools"):
        cleaned["required_tools"] = profile["required_tools"]
    if material_conflicts and profile.get("required_materials"):
        cleaned["required_materials"] = profile["required_materials"]

    estimated_time = str(cleaned.get("estimated_time", ""))
    if _contains_any(_normalize(estimated_time), rules.get("forbidden_time_keywords", ())):
        contradictions.append(f"time: {estimated_time}")
        if profile.get("estimated_time"):
            cleaned["estimated_time"] = profile["estimated_time"]

    professional = str(cleaned.get("recommended_professional_category", ""))
    if _contains_any(_normalize(professional), rules.get("forbidden_professional_keywords", ())):
        contradictions.append(f"professional: {professional}")
        professional_profile = profile.get("recommended_professional_category", {})
        if professional_profile:
            cleaned["recommended_professional_category"] = (
                professional_profile.get("low_risk")
                if risk_level in {"Safe DIY", "DIY with supervision"}
                else professional_profile.get("high_risk")
            ) or professional

    normalized_explanation = _normalize(explanation)
    if _contains_any(normalized_explanation, rules.get("forbidden_explanation_keywords", ())):
        contradictions.append("explanation")
        cleaned["explanation"] = (
            selected_interpretation.strip()
            or rules.get("fallback_explanation", explanation)
        )
    else:
        cleaned["explanation"] = explanation

    if contradictions:
        logger.warning(
            "Recommendation consistency correction applied for task_intent=%s. Contradictions=%s",
            task_intent,
            ", ".join(contradictions),
        )

    return cleaned


def _filter_conflicting_items(
    items: list[str],
    forbidden_keywords: tuple[str, ...],
) -> tuple[list[str], list[str]]:
    if not forbidden_keywords:
        return items, []

    kept: list[str] = []
    removed: list[str] = []
    for item in items:
        if _contains_any(_normalize(item), forbidden_keywords):
            removed.append(item)
        else:
            kept.append(item)
    return kept, removed


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _normalize(value: str) -> str:
    return " ".join(value.lower().strip().split())
