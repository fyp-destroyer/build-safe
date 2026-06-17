from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models import CATEGORY_PROFILES, RISK_LEVELS
from app.schemas import AssessmentRequest, FollowupPlanResponse, RiskLevel
from app.services.task_intent_service import detect_task_intent

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

RUBRIC_MAX = {
    "base_task_risk": 30,
    "hazard_severity": 25,
    "skill_mismatch": 15,
    "tools_ppe_readiness": 15,
    "environment_urgency_unknowns": 15,
}

TASK_BASE_RISK: dict[str, tuple[int, str]] = {
    "hanging_wall_decor": (
        8,
        "Hanging wall decor is usually a low-risk DIY task when the item is light and the wall type is known.",
    ),
    "wall_painting": (
        8,
        "Painting a room is typically a low-risk DIY task if surfaces are sound and ventilation is available.",
    ),
    "electrical_fixture_installation": (
        22,
        "Installing or replacing electrical fixtures is higher risk because wiring isolation and mounting integrity matter.",
    ),
    "electrical_wiring_repair": (
        27,
        "Electrical wiring repair is a high-risk trade task because it can expose live conductors and hidden faults.",
    ),
    "plumbing_leak_repair": (
        18,
        "A plumbing leak repair is a moderate-risk repair task that can escalate if access or shutoff control is poor.",
    ),
    "wall_demolition": (
        27,
        "Wall demolition is a high-risk task because hidden services, debris, and structural uncertainty must be controlled.",
    ),
    "tile_installation": (
        17,
        "Tile installation is a moderate-risk installation task with cutting, surface prep, and waterproofing concerns.",
    ),
    "furniture_assembly": (
        7,
        "Furniture assembly is usually a low-risk DIY task when the item is stable and basic tools are available.",
    ),
    "shelf_installation": (
        14,
        "Shelf installation is a moderate DIY task because fixing strength, wall type, and drilling accuracy matter.",
    ),
    "light_bulb_replacement": (
        6,
        "A like-for-like light bulb replacement is usually low risk when no wiring work is involved.",
    ),
    "ceiling_fan_installation": (
        24,
        "Ceiling fan installation combines electrical work, overhead access, and support-hardware checks.",
    ),
    "hvac_repair": (
        24,
        "HVAC repair is usually a high-risk trade task because sealed systems, electrical parts, or combustion equipment may be involved.",
    ),
    "general_diy": (
        12,
        "This task sits in a moderate DIY band until more task-specific safety details are confirmed.",
    ),
}

CATEGORY_BASE_RISK: dict[str, tuple[int, str]] = {
    "painting": (
        8,
        "Painting is usually low risk compared with most building trade work.",
    ),
    "cleaning": (
        4,
        "Basic cleaning is usually a low-risk task.",
    ),
    "carpentry": (
        12,
        "Carpentry and wall-fixing work are usually moderate risk because anchor strength and hidden services matter.",
    ),
    "plumbing": (
        18,
        "Plumbing repairs are moderate risk because leaks can spread and may affect nearby finishes or utilities.",
    ),
    "tiling": (
        17,
        "Tiling is a moderate installation task with cutting, lifting, and wet-area quality risks.",
    ),
    "masonry_demolition": (
        26,
        "Masonry and demolition tasks are high risk because dust, debris, and hidden services are common hazards.",
    ),
    "electrical": (
        25,
        "Electrical work is high risk because shock, fire, and code-compliance issues can develop quickly.",
    ),
    "hvac": (
        24,
        "HVAC work is high risk because systems can involve electricity, sealed equipment, or combustion.",
    ),
    "roofing": (
        28,
        "Roof work is high risk because height and fall protection dominate the task.",
    ),
    "gas": (
        30,
        "Gas work is treated as the highest task-risk band because leaks can cause explosion or poisoning.",
    ),
    "structural": (
        30,
        "Structural work is treated as the highest task-risk band because incorrect changes can cause collapse.",
    ),
    "general": (
        12,
        "General DIY is kept in a moderate band until the task details are clearer.",
    ),
}

TASK_DIFFICULTY: dict[str, int] = {
    "light_bulb_replacement": 0,
    "hanging_wall_decor": 0,
    "furniture_assembly": 0,
    "wall_painting": 0,
    "shelf_installation": 1,
    "tile_installation": 1,
    "plumbing_leak_repair": 1,
    "electrical_fixture_installation": 2,
    "hvac_repair": 2,
    "ceiling_fan_installation": 2,
    "electrical_wiring_repair": 3,
    "wall_demolition": 3,
    "general_diy": 1,
}

CATEGORY_DIFFICULTY: dict[str, int] = {
    "cleaning": 0,
    "painting": 0,
    "carpentry": 1,
    "tiling": 1,
    "plumbing": 1,
    "electrical": 2,
    "hvac": 2,
    "masonry_demolition": 3,
    "roofing": 3,
    "gas": 3,
    "structural": 3,
    "general": 1,
}

READINESS_EXPECTATIONS: dict[str, dict[str, list[str]]] = {
    "hanging_wall_decor": {
        "items": ["measuring tape", "level", "anchors or hooks"],
        "ppe": ["safety glasses if drilling"],
    },
    "wall_painting": {
        "items": ["paint roller", "brush set", "drop cloth"],
        "ppe": ["mask", "gloves"],
    },
    "electrical_fixture_installation": {
        "items": ["voltage tester", "insulated screwdriver", "stable ladder"],
        "ppe": ["safety glasses", "insulated gloves"],
    },
    "electrical_wiring_repair": {
        "items": ["voltage tester", "insulated screwdriver", "wire stripper"],
        "ppe": ["safety glasses", "insulated gloves"],
    },
    "plumbing_leak_repair": {
        "items": ["adjustable wrench", "bucket", "plumber tape"],
        "ppe": ["waterproof gloves", "eye protection"],
    },
    "wall_demolition": {
        "items": ["stud finder", "hammer", "dust collection bags"],
        "ppe": ["hard hat", "safety goggles", "dust mask"],
    },
    "tile_installation": {
        "items": ["tile cutter", "notched trowel", "level"],
        "ppe": ["safety goggles", "cut-resistant gloves"],
    },
    "furniture_assembly": {
        "items": ["screwdriver set", "hex keys"],
        "ppe": ["work gloves"],
    },
    "shelf_installation": {
        "items": ["drill", "level", "stud finder"],
        "ppe": ["safety glasses", "work gloves"],
    },
    "light_bulb_replacement": {
        "items": ["clean cloth", "stable step stool or ladder if needed"],
        "ppe": ["safety glasses for overhead access"],
    },
    "ceiling_fan_installation": {
        "items": ["voltage tester", "stable ladder", "fan-rated ceiling box"],
        "ppe": ["safety glasses", "insulated gloves"],
    },
    "hvac_repair": {
        "items": ["screwdriver set", "manufacturer guidance", "work light"],
        "ppe": ["safety glasses", "work gloves"],
    },
}

CATEGORY_READINESS_EXPECTATIONS: dict[str, dict[str, list[str]]] = {
    "electrical": {
        "items": ["voltage tester", "insulated screwdriver", "wire stripper"],
        "ppe": ["safety glasses", "insulated gloves"],
    },
    "plumbing": {
        "items": ["adjustable wrench", "bucket", "plumber tape"],
        "ppe": ["waterproof gloves", "eye protection"],
    },
    "masonry_demolition": {
        "items": ["stud finder", "hammer", "dust collection bags"],
        "ppe": ["hard hat", "safety goggles", "dust mask"],
    },
    "tiling": {
        "items": ["tile cutter", "notched trowel", "level"],
        "ppe": ["safety goggles", "cut-resistant gloves"],
    },
    "painting": {
        "items": ["paint roller", "brush set", "drop cloth"],
        "ppe": ["mask", "gloves"],
    },
    "carpentry": {
        "items": ["drill", "level", "stud finder"],
        "ppe": ["safety glasses", "work gloves"],
    },
    "hvac": {
        "items": ["screwdriver set", "work light", "manufacturer guidance"],
        "ppe": ["safety glasses", "work gloves"],
    },
    "roofing": {
        "items": ["extension ladder", "fall arrest kit", "work platform"],
        "ppe": ["non-slip boots", "fall arrest harness"],
    },
    "gas": {
        "items": ["gas leak detector", "adjustable wrench", "shutoff key"],
        "ppe": ["safety glasses", "work gloves"],
    },
    "structural": {
        "items": ["stud finder", "measuring tape", "temporary support equipment"],
        "ppe": ["hard hat", "steel-toe boots"],
    },
    "general": {
        "items": ["measuring tape", "utility knife", "work light"],
        "ppe": ["safety glasses", "work gloves"],
    },
}

SKILL_TIER = {"beginner": 0, "intermediate": 1, "expert": 2}
UNKNOWN_VALUES = {"", "unknown", "not sure", "unsure", "n/a", "na", "none"}


def _load_safety_rules() -> list[dict[str, Any]]:
    with (DATA_DIR / "safety_rules.json").open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return payload["rules"]


def _normalize(value: str) -> str:
    return " ".join(value.lower().strip().split())


def _contains_any(text: str, keywords: list[str] | tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _score_to_level(score: int) -> RiskLevel:
    if score >= 81:
        return RISK_LEVELS[5]
    if score >= 61:
        return RISK_LEVELS[4]
    if score >= 41:
        return RISK_LEVELS[3]
    if score >= 21:
        return RISK_LEVELS[2]
    return RISK_LEVELS[1]


def _risk_level_rank(risk_level: str) -> int:
    for rank, label in RISK_LEVELS.items():
        if label == risk_level:
            return rank
    return 1


def _detect_category(task_text: str) -> str:
    best_category = "general"
    best_score = -1

    for category, profile in CATEGORY_PROFILES.items():
        if category == "general":
            continue
        if _contains_any(task_text, profile.keywords) and profile.base_score > best_score:
            best_category = category
            best_score = profile.base_score

    return best_category


def _answers_missing_or_unknown(answers: dict[str, Any]) -> bool:
    if not answers:
        return True
    return any(_normalize(str(value)) in UNKNOWN_VALUES for value in answers.values())


def assess_risk(
    request: AssessmentRequest,
    llm_analysis: FollowupPlanResponse | None = None,
) -> dict[str, Any]:
    task_text = _normalize(request.task_description)
    skill_level = _resolve_skill_level(request)
    urgency = _normalize(request.urgency)
    normalized_answers = _normalized_answers(request.answers_to_followups)

    intent_result = detect_task_intent(request.task_description)
    task_intent = llm_analysis.task_intent if llm_analysis else intent_result.task_intent
    category = llm_analysis.task_category if llm_analysis else intent_result.task_category
    if category not in CATEGORY_PROFILES:
        category = _detect_category(task_text)

    rules_triggered: list[str] = []
    safety_warnings: list[str] = []
    matched_rule_ids: list[str] = []

    for rule in _load_safety_rules():
        if _contains_any(task_text, rule["keywords"]):
            category = rule.get("category", category)
            matched_rule_ids.append(rule["id"])
            rules_triggered.append(f'{rule["id"]}: {rule["description"]}')
            warning = rule.get("warning")
            if warning:
                safety_warnings.append(warning)

    _apply_answer_signals(
        category=category,
        answers=request.answers_to_followups,
        task_text=task_text,
        rules_triggered=rules_triggered,
        safety_warnings=safety_warnings,
    )

    if llm_analysis and llm_analysis.task_category in CATEGORY_PROFILES:
        category = llm_analysis.task_category
    if llm_analysis:
        safety_warnings.extend(
            _llm_warning_hints(llm_analysis.task_category, llm_analysis.critical_missing_info)
        )

    breakdown = _build_risk_score_breakdown(
        request=request,
        task_intent=task_intent,
        category=category,
        skill_level=skill_level,
        urgency=urgency,
        task_text=task_text,
        normalized_answers=normalized_answers,
        matched_rule_ids=matched_rule_ids,
    )

    threshold_label = breakdown["threshold_label"]
    safety_overrides = _detect_safety_overrides(
        category=category,
        task_text=task_text,
        normalized_answers=normalized_answers,
        matched_rule_ids=matched_rule_ids,
    )
    breakdown["safety_overrides_applied"] = [item["label"] for item in safety_overrides]

    final_rank = max(
        _risk_level_rank(threshold_label),
        max((item["min_level"] for item in safety_overrides), default=1),
    )
    risk_level = RISK_LEVELS[final_rank]

    confidence_score = 0.86 if rules_triggered or request.answers_to_followups else 0.68
    if _answers_missing_or_unknown(request.answers_to_followups):
        confidence_score -= 0.08

    category_label = CATEGORY_PROFILES.get(category, CATEGORY_PROFILES["general"]).label
    explanation = _build_explanation(
        category_label=category_label,
        threshold_label=threshold_label,
        final_risk_level=risk_level,
        total_score=breakdown["total"],
        safety_overrides_applied=breakdown["safety_overrides_applied"],
        rules_triggered=rules_triggered,
        llm_analysis=llm_analysis,
    )

    return {
        "task_intent": task_intent,
        "task_category": category_label,
        "category_key": category,
        "risk_level": risk_level,
        "risk_score": breakdown["total"],
        "risk_score_breakdown": breakdown,
        "confidence_score": round(max(confidence_score, 0.5), 2),
        "explanation": explanation,
        "safety_warnings": _unique(safety_warnings),
        "rules_triggered": _unique(rules_triggered),
    }


def _build_risk_score_breakdown(
    *,
    request: AssessmentRequest,
    task_intent: str,
    category: str,
    skill_level: str,
    urgency: str,
    task_text: str,
    normalized_answers: dict[str, str],
    matched_rule_ids: list[str],
) -> dict[str, Any]:
    base_task_risk = _score_base_task_risk(task_intent=task_intent, category=category)
    hazard_severity = _score_hazard_severity(
        task_intent=task_intent,
        category=category,
        task_text=task_text,
        normalized_answers=normalized_answers,
        matched_rule_ids=matched_rule_ids,
    )
    skill_mismatch = _score_skill_mismatch(
        task_intent=task_intent,
        category=category,
        skill_level=skill_level,
    )
    tools_ppe_readiness = _score_tools_ppe_readiness(
        task_intent=task_intent,
        category=category,
        available_tools=request.available_tools,
    )
    environment_urgency_unknowns = _score_environment_urgency_unknowns(
        category=category,
        urgency=urgency,
        location_type=request.location_type,
        task_text=task_text,
        normalized_answers=normalized_answers,
        answers_provided=request.answers_to_followups,
    )

    total = (
        base_task_risk["points"]
        + hazard_severity["points"]
        + skill_mismatch["points"]
        + tools_ppe_readiness["points"]
        + environment_urgency_unknowns["points"]
    )
    total = min(max(total, 0), 100)

    return {
        "base_task_risk": base_task_risk,
        "hazard_severity": hazard_severity,
        "skill_mismatch": skill_mismatch,
        "tools_ppe_readiness": tools_ppe_readiness,
        "environment_urgency_unknowns": environment_urgency_unknowns,
        "total": total,
        "threshold_label": _score_to_level(total),
        "safety_overrides_applied": [],
    }


def _score_base_task_risk(*, task_intent: str, category: str) -> dict[str, Any]:
    points, reason = TASK_BASE_RISK.get(
        task_intent,
        CATEGORY_BASE_RISK.get(category, CATEGORY_BASE_RISK["general"]),
    )
    return _component(points, RUBRIC_MAX["base_task_risk"], reason)


def _score_hazard_severity(
    *,
    task_intent: str,
    category: str,
    task_text: str,
    normalized_answers: dict[str, str],
    matched_rule_ids: list[str],
) -> dict[str, Any]:
    if task_intent == "light_bulb_replacement":
        if _answer_matches(normalized_answers, ("wiring", "light fitting"), ("wiring", "fitting", "yes")):
            return _component(
                12,
                RUBRIC_MAX["hazard_severity"],
                "The hazard is no longer a simple bulb change because wiring or fitting work may be involved.",
            )
        if _contains_any(task_text, ("ladder", "stairs", "height", "ceiling")):
            return _component(
                7,
                RUBRIC_MAX["hazard_severity"],
                "The main hazards are bulb heat, broken glass, and fall risk from overhead access.",
            )
        return _component(
            4,
            RUBRIC_MAX["hazard_severity"],
            "A standard bulb swap mainly carries minor handling hazards once power is off and the bulb has cooled.",
        )

    if task_intent == "hanging_wall_decor":
        if _contains_any(task_text, ("heavy", "mirror", "tile", "tiled", "bathroom", "drill")):
            return _component(
                11,
                RUBRIC_MAX["hazard_severity"],
                "Risk mainly comes from heavy wall loading, drilling through brittle surfaces, and hidden utilities behind the wall.",
            )
        points = 8 if not _contains_any(task_text, ("adhesive", "command strip")) else 5
        reason = (
            "Risk mainly comes from drilling, falling objects, or hidden utilities in the wall."
        )
        return _component(points, RUBRIC_MAX["hazard_severity"], reason)

    if task_intent == "ceiling_fan_installation" and _answer_matches(
        normalized_answers,
        ("fan-rated", "ceiling box", "existing wiring"),
        ("no", "not sure", "unknown", "unsure"),
    ):
        return _component(
            17,
            RUBRIC_MAX["hazard_severity"],
            "Main hazards include electrical shock, unsupported overhead loading, and uncertainty about the existing wiring or ceiling box.",
        )

    severe_hazards: list[str] = []
    moderate_hazards: list[str] = []

    if "GAS_LINE" in matched_rule_ids or category == "gas":
        severe_hazards.append("gas leak, fire, or explosion")
    if "ELEC_MAIN_PANEL" in matched_rule_ids:
        severe_hazards.append("main-panel electrical exposure")
    if _contains_any(task_text, ("exposed wire", "exposed wiring")):
        severe_hazards.append("exposed live wiring")
    if "STRUCTURAL_LOAD" in matched_rule_ids or _answer_matches(
        normalized_answers,
        ("load-bearing",),
        ("yes", "not sure", "unknown", "unsure"),
    ):
        severe_hazards.append("possible structural collapse")
    if "ROOF_WORK" in matched_rule_ids or category == "roofing":
        severe_hazards.append("fall risk at roof height")
    if _is_water_near_electric(normalized_answers):
        severe_hazards.append("water near electrical equipment")

    if "ELEC_GENERAL" in matched_rule_ids or category == "electrical":
        moderate_hazards.append("shock or fire from electrical work")
    if category == "plumbing" or _contains_any(
        " ".join(matched_rule_ids),
        ("PLUMBING_BASIC_LEAK", "PLUMBING_ACTIVE_EMERGENCY", "PLUMBING_WATER_HEATER"),
    ):
        moderate_hazards.append("water damage or slip hazards")
    if category in {"masonry_demolition", "tiling"} or "DEMOLITION_WALL" in matched_rule_ids:
        moderate_hazards.append("dust, debris, and tool injury")
    if task_intent == "ceiling_fan_installation":
        moderate_hazards.append("overhead mounting and ladder access")
    if _contains_any(task_text, ("ladder", "stairs", "height", "ceiling")):
        moderate_hazards.append("fall risk from height access")
    if _answer_matches(normalized_answers, ("damp", "mold", "peeling"), ("yes",)):
        moderate_hazards.append("surface damage or mold exposure")

    severe_hazards = _unique(severe_hazards)
    moderate_hazards = _unique(moderate_hazards)

    if severe_hazards:
        points = min(25, 19 + (2 * (len(severe_hazards) - 1)))
        reason = f"Main hazards include {', '.join(severe_hazards[:2])}."
        return _component(points, RUBRIC_MAX["hazard_severity"], reason)

    if moderate_hazards:
        points = 12 if len(moderate_hazards) == 1 else min(16, 12 + len(moderate_hazards))
        reason = f"Main hazards include {', '.join(moderate_hazards[:2])}."
        return _component(points, RUBRIC_MAX["hazard_severity"], reason)

    points = 4 if category in {"painting", "cleaning"} else 6
    reason = "Only lower-severity handling hazards are visible from the current task description."
    return _component(points, RUBRIC_MAX["hazard_severity"], reason)


def _score_skill_mismatch(*, task_intent: str, category: str, skill_level: str) -> dict[str, Any]:
    difficulty = TASK_DIFFICULTY.get(task_intent, CATEGORY_DIFFICULTY.get(category, 1))
    skill_tier = SKILL_TIER.get(skill_level, 0)

    if difficulty == 0:
        points = {"beginner": 4, "intermediate": 2, "expert": 1}.get(skill_level, 4)
    elif difficulty == 1:
        points = {"beginner": 8, "intermediate": 5, "expert": 3}.get(skill_level, 8)
    elif difficulty == 2:
        points = {"beginner": 11, "intermediate": 8, "expert": 4}.get(skill_level, 11)
    else:
        points = {"beginner": 15, "intermediate": 10, "expert": 5}.get(skill_level, 15)

    if skill_tier >= difficulty:
        reason = f"The stated {skill_level} skill level broadly matches the task difficulty."
    elif skill_tier + 1 == difficulty:
        reason = f"The stated {skill_level} skill level is somewhat below the task difficulty."
    else:
        reason = f"A {skill_level} user is underqualified for this kind of higher-risk trade work."

    return _component(points, RUBRIC_MAX["skill_mismatch"], reason)


def _score_tools_ppe_readiness(
    *,
    task_intent: str,
    category: str,
    available_tools: list[str],
) -> dict[str, Any]:
    expectation = READINESS_EXPECTATIONS.get(
        task_intent,
        CATEGORY_READINESS_EXPECTATIONS.get(category, CATEGORY_READINESS_EXPECTATIONS["general"]),
    )
    expected_items = expectation["items"]
    expected_ppe = expectation["ppe"]
    normalized_available = [_normalize(tool) for tool in available_tools]
    matched_items = [
        item
        for item in expected_items
        if any(_tool_matches(item, available) for available in normalized_available)
    ]
    missing_items = [item for item in expected_items if item not in matched_items]
    higher_risk_category = category in {"electrical", "masonry_demolition", "hvac", "roofing", "gas", "structural"}

    if task_intent == "light_bulb_replacement":
        if not normalized_available:
            return _component(
                4,
                RUBRIC_MAX["tools_ppe_readiness"],
                "This task needs very limited equipment, but stable access and basic handling care still need to be confirmed.",
            )
        return _component(
            2,
            RUBRIC_MAX["tools_ppe_readiness"],
            "The task needs minimal equipment and the available items appear adequate for a standard bulb change.",
        )

    if not normalized_available:
        points = 12 if higher_risk_category else 8 if category in {"plumbing", "tiling", "carpentry"} else 6
        reason = (
            f"Tool and PPE readiness was not confirmed. Expected items include {', '.join(expected_items[:2])}, "
            f"and PPE such as {', '.join(expected_ppe[:2])} may be needed."
        )
        return _component(points, RUBRIC_MAX["tools_ppe_readiness"], reason)

    if len(matched_items) >= max(1, len(expected_items) - 1):
        points = 3 if higher_risk_category else 2
        reason = "The user appears to have most of the key tools needed, although PPE still needs to be confirmed."
    elif matched_items:
        points = 8 if higher_risk_category else 7
        reason = (
            f"Some key items appear available, but important tools such as {', '.join(missing_items[:2])} "
            "are still missing or unconfirmed."
        )
    else:
        points = 13 if higher_risk_category else 9
        reason = (
            f"The listed tools do not show the main safety-critical items for this task, such as {', '.join(expected_items[:2])}."
        )

    return _component(points, RUBRIC_MAX["tools_ppe_readiness"], reason)


def _score_environment_urgency_unknowns(
    *,
    category: str,
    urgency: str,
    location_type: str,
    task_text: str,
    normalized_answers: dict[str, str],
    answers_provided: dict[str, Any],
) -> dict[str, Any]:
    unknown_count = sum(1 for answer in normalized_answers.values() if answer in UNKNOWN_VALUES)
    load_bearing_unknown = _answer_matches(
        normalized_answers,
        ("load-bearing",),
        ("not sure", "unknown", "unsure"),
    )
    hidden_services_unknown = _answer_matches(
        normalized_answers,
        ("wiring", "plumbing", "gas", "hidden"),
        ("not sure", "unknown", "unsure"),
    )
    drilling_unknowns = category in {"carpentry", "masonry_demolition", "structural"} and (
        not answers_provided or hidden_services_unknown
    )
    apartment_shared_services = location_type == "apartment" and category in {
        "electrical",
        "plumbing",
        "masonry_demolition",
        "gas",
        "structural",
    }

    if urgency == "emergency" or _is_water_near_electric(normalized_answers):
        points = 14
        reason = "The task includes emergency conditions or a combined utility hazard, so the environment is treated conservatively."
        return _component(points, RUBRIC_MAX["environment_urgency_unknowns"], reason)

    if load_bearing_unknown or hidden_services_unknown:
        points = 13
        reason = "Important structural or hidden-utility details are still unknown, which raises site uncertainty."
        return _component(points, RUBRIC_MAX["environment_urgency_unknowns"], reason)

    if drilling_unknowns or urgency == "high":
        points = 10
        reason = "There are still meaningful site unknowns or elevated urgency around access, drilling, or hidden services."
        return _component(points, RUBRIC_MAX["environment_urgency_unknowns"], reason)

    if urgency == "medium" or unknown_count > 0 or apartment_shared_services:
        points = 7
        reason = "Some context is still uncertain, so the environment score stays in the moderate band."
        return _component(points, RUBRIC_MAX["environment_urgency_unknowns"], reason)

    if _contains_any(task_text, ("ladder", "ceiling", "stairs")):
        return _component(
            6,
            RUBRIC_MAX["environment_urgency_unknowns"],
            "Normal conditions appear likely, but access conditions still need basic care.",
        )

    return _component(
        3,
        RUBRIC_MAX["environment_urgency_unknowns"],
        "The environment appears normal, with no urgent issue or major unknown identified.",
    )


def _detect_safety_overrides(
    *,
    category: str,
    task_text: str,
    normalized_answers: dict[str, str],
    matched_rule_ids: list[str],
) -> list[dict[str, Any]]:
    overrides: list[dict[str, Any]] = []

    if "GAS_LINE" in matched_rule_ids or category == "gas":
        overrides.append({"label": "Gas line work", "min_level": 5})
    if "ELEC_MAIN_PANEL" in matched_rule_ids:
        overrides.append({"label": "Main electrical panel", "min_level": 5})
    if _contains_any(task_text, ("exposed wire", "exposed wiring")):
        overrides.append({"label": "Exposed wiring", "min_level": 4})
    if _answer_matches(
        normalized_answers,
        ("load-bearing",),
        ("not sure", "unknown", "unsure"),
    ):
        overrides.append({"label": "Load-bearing wall unknown", "min_level": 5})
    if category == "structural" or "STRUCTURAL_LOAD" in matched_rule_ids:
        overrides.append({"label": "Structural demolition", "min_level": 5})
    if "ROOF_WORK" in matched_rule_ids or category == "roofing":
        overrides.append({"label": "Roof work at height", "min_level": 4})
    if _is_water_near_electric(normalized_answers):
        overrides.append({"label": "Water leakage near electricity", "min_level": 4})
    if category in {"masonry_demolition", "structural"} and _answer_matches(
        normalized_answers,
        ("wiring", "plumbing", "gas", "hidden"),
        ("yes", "not sure", "unknown", "unsure"),
    ):
        overrides.append({"label": "Unknown hidden utilities during demolition/drilling", "min_level": 4})

    return _dedupe_overrides(overrides)


def _build_explanation(
    *,
    category_label: str,
    threshold_label: str,
    final_risk_level: str,
    total_score: int,
    safety_overrides_applied: list[str],
    rules_triggered: list[str],
    llm_analysis: FollowupPlanResponse | None,
) -> str:
    lead = (
        llm_analysis.short_reason
        if llm_analysis and llm_analysis.short_reason
        else f"This task was classified as {category_label.lower()}."
    )

    if safety_overrides_applied:
        overrides = ", ".join(safety_overrides_applied[:2])
        return (
            f"{lead} The rubric totaled {total_score}/100, which maps to {threshold_label.lower()}, "
            f"but the final result was escalated to {final_risk_level.lower()} because of these safety override triggers: {overrides}."
        )

    if rules_triggered:
        return (
            f"{lead} The rubric totaled {total_score}/100, which places it in the "
            f"{final_risk_level.lower()} tier after matching one or more safety signals."
        )

    return (
        f"{lead} The rubric totaled {total_score}/100, which places it in the "
        f"{final_risk_level.lower()} tier."
    )


def _component(points: int, max_points: int, reason: str) -> dict[str, Any]:
    return {
        "points": min(max(points, 0), max_points),
        "max": max_points,
        "reason": reason,
    }


def _normalized_answers(answers: dict[str, Any]) -> dict[str, str]:
    return {_normalize(str(question)): _normalize(str(answer)) for question, answer in answers.items()}


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _dedupe_overrides(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        label = str(value["label"])
        if label in seen:
            continue
        seen.add(label)
        unique.append(value)
    return unique


def _resolve_skill_level(request: AssessmentRequest) -> str:
    explicit_skill = _normalize(request.user_skill_level)
    if explicit_skill != "beginner":
        return explicit_skill

    for question, answer in request.answers_to_followups.items():
        normalized_question = _normalize(str(question))
        normalized_answer = _normalize(str(answer))
        if "skill level" not in normalized_question and "experience level" not in normalized_question:
            continue
        if normalized_answer in {"beginner", "intermediate", "expert"}:
            return normalized_answer

    return explicit_skill


def _tool_matches(expected_item: str, available_tool: str) -> bool:
    expected_tokens = [token for token in _normalize(expected_item).replace("/", " ").split() if len(token) > 2]
    if not expected_tokens:
        return False
    return any(token in available_tool for token in expected_tokens)


def _is_water_near_electric(normalized_answers: dict[str, str]) -> bool:
    return _answer_matches(
        normalized_answers,
        ("electrical", "outlet", "switch", "appliance"),
        ("yes",),
    )


def _apply_answer_signals(
    *,
    category: str,
    answers: dict[str, Any],
    task_text: str,
    rules_triggered: list[str],
    safety_warnings: list[str],
) -> int:
    adjustment = 0
    normalized_answers = _normalized_answers(answers)

    if category == "electrical":
        if _answer_matches(normalized_answers, ("wiring", "light fitting"), ("yes", "wiring", "fitting")):
            adjustment += 12
            rules_triggered.append(
                "ANSWER_WIRING_INVOLVED: The follow-up answers indicate wiring or fitting work."
            )
            safety_warnings.append(
                "Do not proceed as a simple DIY swap if the task involves wiring, fittings, or unknown live conductors."
            )
        if _answer_matches(
            normalized_answers,
            ("fan-rated", "ceiling box", "existing wiring"),
            ("no", "not sure", "unknown", "unsure"),
        ):
            adjustment += 8
            rules_triggered.append(
                "ANSWER_UNKNOWN_FAN_SUPPORT: Existing wiring or fixture support is unsuitable or unknown."
            )
        if _answer_matches(normalized_answers, ("ladder", "height"), ("yes",)):
            adjustment += 6
            rules_triggered.append(
                "ANSWER_HEIGHT_ACCESS: Height access increases fall risk during electrical or fixture work."
            )

    if category in {"plumbing", "general"}:
        if _answer_matches(normalized_answers, ("electrical", "outlet", "switch", "appliance"), ("yes",)):
            adjustment = max(adjustment, 18)
            rules_triggered.append(
                "ANSWER_WATER_NEAR_ELECTRIC: Water near electrical equipment raises the task into a higher-risk tier."
            )
            safety_warnings.append(
                "Water near outlets, switches, or appliances should be treated as a combined plumbing and electrical hazard."
            )
        if _answer_matches(normalized_answers, ("hidden", "main line"), ("hidden", "main", "yes")):
            adjustment += 10
            rules_triggered.append(
                "ANSWER_HIDDEN_LEAK_PATH: Hidden or main-line leaks need more conservative assessment."
            )
        if _answer_matches(normalized_answers, ("minor visible joint leak", "visible joint"), ("minor", "visible")):
            adjustment -= 12
            rules_triggered.append(
                "ANSWER_ACCESSIBLE_MINOR_LEAK: The leak appears accessible and limited."
            )

    if category in {"masonry_demolition", "structural"}:
        if _answer_matches(normalized_answers, ("load-bearing",), ("yes", "not sure", "unknown", "unsure")):
            adjustment = max(adjustment, 18)
            rules_triggered.append(
                "ANSWER_STRUCTURAL_UNCERTAINTY: Possible load-bearing work requires structural review."
            )
            safety_warnings.append(
                "Do not start demolition while the load-bearing status is uncertain."
            )
        if _answer_matches(
            normalized_answers,
            ("wiring", "plumbing", "gas"),
            ("yes", "not sure", "unknown", "unsure"),
        ):
            adjustment += 10
            rules_triggered.append(
                "ANSWER_HIDDEN_SERVICES: Hidden service uncertainty raises demolition risk."
            )

    if category == "painting":
        if _answer_matches(normalized_answers, ("damp", "mold", "peeling"), ("yes",)):
            adjustment += 8
            rules_triggered.append(
                "ANSWER_SURFACE_DAMAGE: Dampness, mold, or peeling paint complicates a basic repaint."
            )
            safety_warnings.append(
                "Moisture damage, mold, or failing paint should be addressed before repainting."
            )
        if _contains_any(task_text, ("ceiling", "stairs", "height")):
            adjustment += 4

    return adjustment


def _answer_matches(
    normalized_answers: dict[str, str],
    question_tokens: tuple[str, ...],
    answer_tokens: tuple[str, ...],
) -> bool:
    for question, answer in normalized_answers.items():
        if not any(token in question for token in question_tokens):
            continue
        if any(token in answer for token in answer_tokens):
            return True
    return False


def _llm_warning_hints(task_category: str, critical_missing_info: list[str]) -> list[str]:
    if not critical_missing_info:
        return []

    label = CATEGORY_PROFILES.get(task_category, CATEGORY_PROFILES["general"]).label
    return [
        f"Some important {label.lower()} details are still unknown: {', '.join(critical_missing_info[:2])}."
    ]
