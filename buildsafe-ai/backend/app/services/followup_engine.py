from __future__ import annotations

from typing import Any

from app.schemas import TaskIntent

QUESTION_BANK: dict[str, list[tuple[str, str]]] = {
    "hanging_wall_decor": [
        ("painting_weight", "How heavy is the artwork or frame, and does it need anchors into the wall?"),
        ("wall_material", "What wall material are you fixing into, and will you drill or use adhesive hardware?"),
    ],
    "electrical": [
        ("power_isolated", "Can the circuit be switched off and verified with a voltage tester?"),
        ("main_panel_involved", "Does the task involve the main electrical panel, breaker panel, or service line?"),
        ("fixture_support", "For fixtures or fans, is the mounting box rated for the fixture weight and movement?"),
    ],
    "plumbing": [
        ("water_shutoff", "Can you shut off the local valve or main water supply before starting?"),
        ("active_leak", "Is the leak active, spreading, or near electrical outlets?"),
        ("hidden_pipe", "Is the pipe inside a wall, ceiling, or floor cavity?"),
    ],
    "masonry_demolition": [
        ("load_bearing_checked", "Has the wall or surface been confirmed non-load-bearing?"),
        ("hidden_services_checked", "Could electrical wiring, plumbing, or gas lines be behind the surface?"),
        ("permit_checked", "Does the work require building approval or a local permit?"),
    ],
    "tiling": [
        ("surface_prepared", "Is the surface clean, flat, waterproofed if needed, and structurally sound?"),
        ("wet_area", "Is this tiling in a shower, bathroom, balcony, or other wet area?"),
        ("hidden_services_checked", "Have you checked for hidden wiring or plumbing before cutting or drilling?"),
    ],
    "painting": [
        ("ventilation", "Can the room be ventilated during painting and drying?"),
        ("lead_paint", "Is there old peeling paint that could contain lead?"),
        ("height_work", "Will you paint at height, above stairs, or near an open edge?"),
    ],
    "carpentry": [
        ("wall_type", "What type of wall or surface will hold the shelf, cabinet, or fixture?"),
        ("weight_load", "What load will the installed item need to support?"),
        ("hidden_services_checked", "Have you checked for hidden wiring or plumbing before drilling?"),
    ],
    "hvac": [
        ("refrigerant_involved", "Does the task involve refrigerant lines, compressor work, or sealed AC components?"),
        ("dedicated_circuit", "Does the unit require a dedicated electrical circuit or breaker work?"),
        ("manufacturer_manual", "Do you have the manufacturer manual and correct filter or replacement part?"),
    ],
    "roofing": [
        ("fall_protection", "Do you have suitable fall protection and stable access?"),
        ("weather_safe", "Is the roof dry and weather safe for access?"),
        ("roof_height", "How high is the roof edge from ground level?"),
    ],
    "gas": [
        ("gas_shutoff", "Can the gas supply be shut off safely before any inspection?"),
        ("gas_smell", "Is there a gas smell, hissing sound, or suspected active leak?"),
        ("licensed_trade", "Is a licensed gas technician available for the work?"),
    ],
    "structural": [
        ("engineer_review", "Has a structural engineer reviewed the change?"),
        ("permit_checked", "Does the work require a permit or building approval?"),
        ("temporary_support", "Is temporary support needed before modifying the structure?"),
    ],
    "general": [
        ("work_area_safe", "Is the work area dry, stable, and clear of trip hazards?"),
        ("right_tools", "Do you have the correct tools in good working condition?"),
    ],
}


def get_follow_up_questions(
    task_intent: TaskIntent,
    category_key: str,
    answers: dict[str, Any],
) -> list[str]:
    if answers and not any(
        str(value).strip().lower() in {"", "unknown", "not sure", "unsure"}
        for value in answers.values()
    ):
        return []

    questions = QUESTION_BANK.get(task_intent) or QUESTION_BANK.get(category_key, QUESTION_BANK["general"])
    answered_keys = {
        key for key, value in answers.items() if str(value).strip().lower() not in {"", "unknown", "not sure", "unsure"}
    }
    return [question for key, question in questions if key not in answered_keys][:2]
