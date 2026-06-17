from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv

from app.schemas import AssessmentRequest, FollowupPlanResponse
from app.services.recommendation_engine import (
    get_recommendations,
    validate_assessment_consistency,
)
from app.services.risk_engine import assess_risk
from app.services.task_intent_service import category_for_intent

load_dotenv()
logger = logging.getLogger(__name__)

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"

SECTION_MAP: dict[str, list[str]] = {
    "painting_weight": ["risk_score", "materials", "safety_warnings"],
    "item_weight": ["risk_score", "materials", "safety_warnings"],
    "wall_material": ["risk_score", "materials", "basic_tools", "estimated_time", "safety_warnings"],
    "attachment_method": ["risk_score", "materials", "basic_tools", "safety_warnings"],
    "hidden_utilities": ["risk_score", "safety_warnings", "professional_recommendation"],
    "available_tools": ["basic_tools", "risk_score"],
    "unavailable_tools": ["basic_tools", "risk_score"],
    "user_skill_level": ["risk_score", "safety_warnings"],
    "electrical_damage": ["task_intent", "risk_score", "safety_warnings", "professional_recommendation"],
}
ALL_SECTIONS = [
    "task_intent",
    "task_category",
    "risk_score",
    "risk_level",
    "materials",
    "basic_tools",
    "ppe",
    "estimated_time",
    "safety_warnings",
    "professional_recommendation",
    "action_plan",
]

RISK_LEVEL_RANK: dict[str, int] = {
    "Safe DIY": 1,
    "DIY with supervision": 2,
    "Professional recommended": 3,
    "Professional required": 4,
    "Dangerous / permit-required / do not attempt": 5,
}
RISK_LEVEL_BY_RANK = {rank: label for label, rank in RISK_LEVEL_RANK.items()}


@dataclass(frozen=True)
class AssessmentUpdateParseResult:
    detected_updates: list[dict[str, Any]]
    affected_sections: list[str]
    likely_unchanged_sections: list[str]
    needs_reassessment: bool
    requires_more_information: bool
    follow_up_questions: list[str]
    short_reason: str
    gemini_enabled: bool
    gemini_used: bool
    fallback_used: bool
    parser_source: str
    gemini_model: str
    gemini_error: str | None = None


@dataclass(frozen=True)
class MergedAssessmentContext:
    task_description: str
    task_intent: str
    task_category: str
    previous_answers: dict[str, Any]
    current_user_context: dict[str, Any]


@dataclass(frozen=True)
class AssessmentUpdateResult:
    updated_assessment: dict[str, Any]
    detected_updates: list[dict[str, Any]]
    changed_sections: list[str]
    unchanged_sections: list[str]
    affected_sections: list[str]
    likely_unchanged_sections: list[str]
    risk_score_change: dict[str, Any]
    risk_level_change: dict[str, Any]
    assistant_message: str
    needs_reassessment: bool
    requires_more_information: bool
    follow_up_questions: list[str]
    gemini_enabled: bool
    gemini_used: bool
    fallback_used: bool
    parser_source: str
    gemini_model: str
    gemini_error: str | None = None


def process_assessment_update(
    *,
    previous_assessment: dict[str, Any],
    task_description: str,
    task_intent: str,
    task_category: str,
    previous_answers: dict[str, Any],
    update_message: str,
    current_user_context: dict[str, Any],
) -> AssessmentUpdateResult:
    parsed_update = parse_assessment_update(
        previous_assessment=previous_assessment,
        task_description=task_description,
        task_intent=task_intent,
        task_category=task_category,
        previous_answers=previous_answers,
        update_message=update_message,
        current_user_context=current_user_context,
    )
    merged_context = merge_update_context(
        task_description=task_description,
        task_intent=task_intent,
        task_category=task_category,
        previous_answers=previous_answers,
        current_user_context=current_user_context,
        detected_updates=parsed_update.detected_updates,
    )
    updated_assessment = reassess_with_merged_context(
        previous_assessment=previous_assessment,
        merged_context=merged_context,
        detected_updates=parsed_update.detected_updates,
    )
    comparison = compare_assessments(
        previous_assessment=previous_assessment,
        updated_assessment=updated_assessment,
        parser_affected_sections=parsed_update.affected_sections,
        parser_likely_unchanged_sections=parsed_update.likely_unchanged_sections,
        detected_updates=parsed_update.detected_updates,
    )

    return AssessmentUpdateResult(
        updated_assessment=updated_assessment,
        detected_updates=parsed_update.detected_updates,
        changed_sections=comparison["changed_sections"],
        unchanged_sections=comparison["unchanged_sections"],
        affected_sections=comparison["changed_sections"],
        likely_unchanged_sections=comparison["unchanged_sections"],
        risk_score_change=comparison["risk_score_change"],
        risk_level_change=comparison["risk_level_change"],
        assistant_message=_build_update_assistant_message(
            parsed_update.detected_updates,
            comparison["changed_sections"],
            comparison["risk_score_change"],
            comparison["risk_level_change"],
            parsed_update.requires_more_information,
        ),
        needs_reassessment=parsed_update.needs_reassessment,
        requires_more_information=parsed_update.requires_more_information,
        follow_up_questions=parsed_update.follow_up_questions,
        gemini_enabled=parsed_update.gemini_enabled,
        gemini_used=parsed_update.gemini_used,
        fallback_used=parsed_update.fallback_used,
        parser_source=parsed_update.parser_source,
        gemini_model=parsed_update.gemini_model,
        gemini_error=parsed_update.gemini_error,
    )


def parse_assessment_update(
    *,
    previous_assessment: dict[str, Any],
    task_description: str,
    task_intent: str,
    task_category: str,
    previous_answers: dict[str, Any],
    update_message: str,
    current_user_context: dict[str, Any],
) -> AssessmentUpdateParseResult:
    gemini_enabled = _gemini_enabled()
    gemini_model = _gemini_model()

    if gemini_enabled:
        logger.info("Gemini assessment update parsing attempt started. model=%s", gemini_model)
        gemini_result, gemini_trace = _parse_with_gemini(
            previous_assessment=previous_assessment,
            task_description=task_description,
            task_intent=task_intent,
            task_category=task_category,
            previous_answers=previous_answers,
            update_message=update_message,
            current_user_context=current_user_context,
            gemini_model=gemini_model,
        )
        if gemini_result is not None:
            logger.info("Gemini assessment update parsing succeeded. model=%s", gemini_model)
            return gemini_result

        logger.warning(
            "Gemini assessment update parsing failed. model=%s reason=%s",
            gemini_model,
            gemini_trace.get("gemini_error") or "unknown",
        )
        return _parse_with_fallback(
            previous_assessment=previous_assessment,
            task_intent=task_intent,
            previous_answers=previous_answers,
            update_message=update_message,
            current_user_context=current_user_context,
            gemini_enabled=gemini_enabled,
            gemini_model=gemini_model,
            gemini_error=gemini_trace.get("gemini_error"),
        )

    return _parse_with_fallback(
        previous_assessment=previous_assessment,
        task_intent=task_intent,
        previous_answers=previous_answers,
        update_message=update_message,
        current_user_context=current_user_context,
        gemini_enabled=gemini_enabled,
        gemini_model=gemini_model,
        gemini_error=None,
    )


def merge_update_context(
    *,
    task_description: str,
    task_intent: str,
    task_category: str,
    previous_answers: dict[str, Any],
    current_user_context: dict[str, Any],
    detected_updates: list[dict[str, Any]],
) -> MergedAssessmentContext:
    merged_answers = dict(previous_answers)
    merged_context = dict(current_user_context)
    merged_task_description = task_description

    weight = _first_update_value(detected_updates, {"painting_weight", "item_weight"})
    wall_material = _first_update_value(detected_updates, {"wall_material"})
    attachment_method = _first_update_value(detected_updates, {"attachment_method"})
    hidden_utilities = _first_update_value(detected_updates, {"hidden_utilities"})
    electrical_damage = _first_update_value(detected_updates, {"electrical_damage"})

    if weight is not None:
        merged_answers[_weight_question_for_intent(task_intent)] = str(weight)

    if wall_material is not None or attachment_method is not None:
        wall_answer = _merge_wall_and_attachment_answer(
            previous_answers=merged_answers,
            wall_material=wall_material,
            attachment_method=attachment_method,
        )
        merged_answers[_wall_method_question_for_intent(task_intent)] = wall_answer

    if hidden_utilities:
        utilities_text = ", ".join(_as_string_list(hidden_utilities))
        merged_answers[
            "Could there be wiring, plumbing, or gas lines behind the wall or fixing area?"
        ] = f"not sure - possible {utilities_text}"
        merged_task_description = _append_context_once(
            merged_task_description,
            f"Updated safety concern: possible hidden {utilities_text} behind the wall.",
        )

    if electrical_damage:
        damage_text = ", ".join(_as_string_list(electrical_damage))
        merged_answers[
            "Does this involve exposed wiring, a damaged holder, or a broken socket?"
        ] = f"yes - {damage_text}"
        merged_task_description = _append_context_once(
            merged_task_description,
            f"Updated safety concern: exposed wires and damaged electrical holder/socket reported.",
        )

    skill_level = _first_update_value(detected_updates, {"user_skill_level"})
    if isinstance(skill_level, str) and skill_level in {"beginner", "intermediate", "expert"}:
        merged_context["user_skill_level"] = skill_level
        merged_answers["What is your experience level with this task?"] = skill_level

    available_tools = list(merged_context.get("available_tools") or [])
    new_tools = _first_update_value(detected_updates, {"available_tools"})
    if new_tools:
        available_tools = _unique_strings([*available_tools, *_as_string_list(new_tools)])
    unavailable_tools = _first_update_value(detected_updates, {"unavailable_tools"})
    if unavailable_tools:
        unavailable = {_normalize(tool) for tool in _as_string_list(unavailable_tools)}
        available_tools = [
            tool for tool in available_tools if _normalize(str(tool)) not in unavailable
        ]
        merged_answers["Which expected tools or PPE are missing?"] = ", ".join(
            _as_string_list(unavailable_tools)
        )
    merged_context["available_tools"] = available_tools

    normalized_intent = _normalize_task_intent(task_intent)
    return MergedAssessmentContext(
        task_description=merged_task_description,
        task_intent=normalized_intent,
        task_category=_normalize_category_key(task_category, normalized_intent),
        previous_answers=merged_answers,
        current_user_context=merged_context,
    )


def reassess_with_merged_context(
    *,
    previous_assessment: dict[str, Any],
    merged_context: MergedAssessmentContext,
    detected_updates: list[dict[str, Any]],
) -> dict[str, Any]:
    request = AssessmentRequest(
        task_description=merged_context.task_description,
        user_skill_level=_normalize_skill_level(
            merged_context.current_user_context.get("user_skill_level")
        ),
        available_tools=[
            str(tool)
            for tool in merged_context.current_user_context.get("available_tools", [])
            if str(tool).strip()
        ],
        location_type=_normalize_location_type(
            merged_context.current_user_context.get("location_type")
        ),
        urgency=_normalize_urgency(merged_context.current_user_context.get("urgency")),
        budget_range=str(
            merged_context.current_user_context.get("budget_range", "not specified")
        ),
        answers_to_followups=merged_context.previous_answers,
    )
    frozen_analysis = FollowupPlanResponse(
        task_intent=merged_context.task_intent,
        task_category=merged_context.task_category,
        is_ambiguous=False,
        possible_interpretations=[],
        selected_interpretation=(
            "The update is being applied to the existing assessment session; task intent is preserved unless explicitly changed."
        ),
        risk_factors=_risk_factors_for_updates(detected_updates),
        critical_missing_info=[],
        follow_up_questions=[],
        suggested_risk_level=_normalize_risk_level(previous_assessment.get("risk_level")),
        short_reason=_build_short_reason(detected_updates, requires_more_information=False),
        llm_used=False,
    )

    risk_result = assess_risk(request, llm_analysis=frozen_analysis)
    category_key = risk_result.pop("category_key")
    recommendations = get_recommendations(
        category_key,
        risk_result["risk_level"],
        risk_result["task_intent"],
    )
    consistency_checked = validate_assessment_consistency(
        task_intent=risk_result["task_intent"],
        explanation=risk_result["explanation"],
        recommendations=recommendations,
        selected_interpretation=frozen_analysis.selected_interpretation,
        risk_level=risk_result["risk_level"],
    )

    updated = {
        **risk_result,
        "follow_up_questions": [],
        "required_tools": consistency_checked["required_tools"],
        "required_materials": consistency_checked["required_materials"],
        "required_ppe": consistency_checked["required_ppe"],
        "estimated_time": consistency_checked["estimated_time"],
        "estimated_cost_range": consistency_checked["estimated_cost_range"],
        "recommended_professional_category": consistency_checked[
            "recommended_professional_category"
        ],
        "debug_trace": None,
    }
    return _apply_update_specific_assessment_adjustments(
        previous_assessment=previous_assessment,
        updated_assessment=updated,
        detected_updates=detected_updates,
    )


def compare_assessments(
    *,
    previous_assessment: dict[str, Any],
    updated_assessment: dict[str, Any],
    parser_affected_sections: list[str],
    parser_likely_unchanged_sections: list[str],
    detected_updates: list[dict[str, Any]],
) -> dict[str, Any]:
    actual_changed_sections: list[str] = []
    section_fields = {
        "task_intent": "task_intent",
        "task_category": "task_category",
        "risk_score": "risk_score",
        "risk_level": "risk_level",
        "basic_tools": "required_tools",
        "materials": "required_materials",
        "ppe": "required_ppe",
        "safety_warnings": "safety_warnings",
        "professional_recommendation": "recommended_professional_category",
        "estimated_time": "estimated_time",
    }

    for section, field in section_fields.items():
        if _values_differ(previous_assessment.get(field), updated_assessment.get(field)):
            actual_changed_sections.append(section)

    changed_sections = list(
        dict.fromkeys([*actual_changed_sections, *parser_affected_sections])
    )
    if not detected_updates:
        changed_sections = actual_changed_sections

    unchanged_sections = [
        section
        for section in ALL_SECTIONS
        if section not in set(changed_sections)
    ]
    for section in parser_likely_unchanged_sections:
        if section not in changed_sections and section not in unchanged_sections:
            unchanged_sections.append(section)

    old_score = _safe_int(previous_assessment.get("risk_score"))
    new_score = _safe_int(updated_assessment.get("risk_score"))
    old_level = str(previous_assessment.get("risk_level") or "Unknown")
    new_level = str(updated_assessment.get("risk_level") or "Unknown")

    return {
        "changed_sections": changed_sections,
        "unchanged_sections": unchanged_sections,
        "risk_score_change": {
            "old_score": old_score,
            "new_score": new_score,
            "changed": old_score != new_score,
            "reason": _risk_score_change_reason(detected_updates, old_score, new_score),
        },
        "risk_level_change": {
            "old_level": old_level,
            "new_level": new_level,
            "changed": old_level != new_level,
            "reason": _risk_level_change_reason(detected_updates, old_level, new_level),
        },
    }


def _apply_update_specific_assessment_adjustments(
    *,
    previous_assessment: dict[str, Any],
    updated_assessment: dict[str, Any],
    detected_updates: list[dict[str, Any]],
) -> dict[str, Any]:
    adjusted = dict(updated_assessment)
    adjusted["required_tools"] = list(adjusted.get("required_tools") or [])
    adjusted["required_materials"] = list(adjusted.get("required_materials") or [])
    adjusted["required_ppe"] = list(adjusted.get("required_ppe") or [])
    adjusted["safety_warnings"] = list(adjusted.get("safety_warnings") or [])
    score_delta = 0
    minimum_risk_rank = 1
    adjustment_reasons: list[str] = []

    for update in detected_updates:
        field = str(update.get("field"))
        value = update.get("new_value")

        if field in {"painting_weight", "item_weight"}:
            delta = _weight_score_delta(value)
            score_delta += delta
            if delta > 0:
                adjustment_reasons.append("The item weight needs stronger fixing checks.")
            weight_label = str(value)
            adjusted["required_materials"] = _unique_strings(
                [
                    *adjusted["required_materials"],
                    f"fixings rated above {weight_label}",
                    "heavier-duty wall anchors if drilling is used",
                ]
            )
            adjusted["safety_warnings"] = _unique_strings(
                [
                    *adjusted["safety_warnings"],
                    f"Confirm the selected hook, anchor, or adhesive product is rated above {weight_label}.",
                ]
            )

        elif field == "wall_material":
            material = _normalize(str(value))
            if material in {"concrete", "brick", "tiled wall"}:
                score_delta += 5
                adjustment_reasons.append(
                    "The wall material needs more robust fixings and drilling control."
                )
                adjusted["required_tools"] = _unique_strings(
                    [
                        *adjusted["required_tools"],
                        "masonry drill bit",
                        "hammer drill if drilling into masonry",
                    ]
                )
                anchor_label = (
                    "concrete anchors or masonry plugs"
                    if material == "concrete"
                    else "masonry anchors or wall plugs"
                )
                adjusted["required_materials"] = _unique_strings(
                    [*adjusted["required_materials"], anchor_label]
                )
                adjusted["estimated_time"] = (
                    "30-90 minutes depending on masonry drilling, dust control, and fixing selection"
                )
                adjusted["safety_warnings"] = _unique_strings(
                    [
                        *adjusted["safety_warnings"],
                        "Use fixings rated for the wall material and stop if the surface cracks or crumbles.",
                    ]
                )
            elif material in {"plaster", "wooden wall"}:
                score_delta += 2

        elif field == "attachment_method":
            method = _normalize(str(value))
            if "adhesive" in method:
                score_delta -= 2
                adjusted["required_tools"] = [
                    tool
                    for tool in adjusted["required_tools"]
                    if "drill" not in _normalize(str(tool))
                ]
                adjusted["required_materials"] = _unique_strings(
                    [
                        item
                        for item in adjusted["required_materials"]
                        if not _contains_any(
                            _normalize(str(item)),
                            ("screw", "wall plug", "anchor", "hanging wire"),
                        )
                    ]
                    + [
                        "adhesive strips rated for the item weight",
                        "surface cleaning wipes for adhesive preparation",
                    ]
                )
                adjusted["safety_warnings"] = _unique_strings(
                    [
                        *adjusted["safety_warnings"],
                        "Check the adhesive manufacturer's weight limit and surface compatibility before relying on strips.",
                    ]
                )
            elif method in {"drilling", "anchors", "screws"}:
                score_delta += 4
                adjusted["required_tools"] = _unique_strings(
                    [*adjusted["required_tools"], "drill", "stud finder or utility detector"]
                )
                adjusted["safety_warnings"] = _unique_strings(
                    [
                        *adjusted["safety_warnings"],
                        "Check for hidden wiring, plumbing, or gas lines before drilling.",
                    ]
                )

        elif field == "hidden_utilities":
            utilities = _as_string_list(value)
            score_delta += 18
            if any("gas" in _normalize(item) for item in utilities):
                minimum_risk_rank = max(minimum_risk_rank, 5)
            else:
                minimum_risk_rank = max(minimum_risk_rank, 3)
            adjustment_reasons.append("Possible hidden utilities increase the consequence of drilling or cutting.")
            adjusted["safety_warnings"] = _unique_strings(
                [
                    *adjusted["safety_warnings"],
                    "Do not drill, cut, or open the wall until hidden wiring, plumbing, or gas services are ruled out.",
                ]
            )
            adjusted["recommended_professional_category"] = (
                "Electrician or qualified handyman recommended before drilling near suspected hidden services"
            )

        elif field == "unavailable_tools":
            missing = ", ".join(_as_string_list(value))
            score_delta += 8
            adjusted["safety_warnings"] = _unique_strings(
                [
                    *adjusted["safety_warnings"],
                    f"Do not proceed until missing safety-critical tools or PPE are available: {missing}.",
                ]
            )

        elif field == "user_skill_level":
            if str(value) == "beginner":
                score_delta += 3

        elif field == "electrical_damage":
            score_delta += 25
            minimum_risk_rank = max(minimum_risk_rank, 4)
            adjustment_reasons.append("Exposed wires or damaged electrical parts require conservative escalation.")
            adjusted["required_ppe"] = _unique_strings(
                [*adjusted["required_ppe"], "insulated gloves for professional inspection"]
            )
            adjusted["safety_warnings"] = _unique_strings(
                [
                    *adjusted["safety_warnings"],
                    "Do not touch exposed wires, damaged holders, or broken sockets; isolate power and call a qualified electrician.",
                ]
            )
            adjusted["recommended_professional_category"] = "Licensed electrician"

    old_score = _safe_int(previous_assessment.get("risk_score"))
    engine_score = _safe_int(adjusted.get("risk_score")) or 0
    new_score = max(0, min(100, engine_score + score_delta))
    if score_delta > 0 and old_score is not None:
        new_score = max(new_score, min(100, old_score + score_delta))
    elif score_delta < 0 and old_score is not None:
        new_score = max(0, min(new_score, old_score + score_delta))

    adjusted["risk_score"] = new_score
    score_rank = _risk_rank(_score_to_level(new_score))
    final_rank = max(score_rank, minimum_risk_rank)
    adjusted["risk_level"] = RISK_LEVEL_BY_RANK[final_rank]
    _sync_breakdown_total(adjusted, new_score, adjustment_reasons)
    return adjusted


def _sync_breakdown_total(
    assessment: dict[str, Any],
    new_score: int | None,
    adjustment_reasons: list[str],
) -> None:
    if new_score is None:
        return
    breakdown = assessment.get("risk_score_breakdown")
    if not isinstance(breakdown, dict):
        return
    breakdown["total"] = new_score
    breakdown["threshold_label"] = _score_to_level(new_score)
    if adjustment_reasons:
        overrides = list(breakdown.get("safety_overrides_applied") or [])
        overrides.extend(adjustment_reasons)
        breakdown["safety_overrides_applied"] = _unique_strings(overrides)


def _build_update_assistant_message(
    detected_updates: list[dict[str, Any]],
    changed_sections: list[str],
    risk_score_change: dict[str, Any],
    risk_level_change: dict[str, Any],
    requires_more_information: bool,
) -> str:
    if not detected_updates:
        return "I received the update, but I could not detect a structured assessment change yet."

    changed_label = ", ".join(changed_sections[:4]) if changed_sections else "the assessment context"
    score_text = (
        f" Risk score changed from {risk_score_change['old_score']} to {risk_score_change['new_score']}."
        if risk_score_change.get("changed")
        else " Risk score stayed the same."
    )
    level_text = (
        f" Risk level changed from {risk_level_change['old_level']} to {risk_level_change['new_level']}."
        if risk_level_change.get("changed")
        else " Risk level stayed the same."
    )
    clarification_text = (
        " I need one clarification before the next reassessment step."
        if requires_more_information
        else ""
    )
    return (
        f"I applied your update and reassessed the existing task. Relevant changed sections: {changed_label}."
        f"{score_text}{level_text}{clarification_text}"
    )


def _risk_factors_for_updates(detected_updates: list[dict[str, Any]]) -> list[str]:
    labels = {
        "painting_weight": "Updated item weight",
        "item_weight": "Updated item weight",
        "wall_material": "Updated wall material",
        "attachment_method": "Updated attachment method",
        "hidden_utilities": "Possible hidden utilities",
        "available_tools": "Updated tool availability",
        "unavailable_tools": "Missing tools or PPE",
        "user_skill_level": "Updated user skill level",
        "electrical_damage": "Damaged electrical item or exposed wires",
    }
    return _unique_strings([labels.get(str(update.get("field")), str(update.get("field"))) for update in detected_updates])


def _weight_score_delta(value: Any) -> int:
    text = _normalize(str(value))
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*kg\b", text)
    if match:
        weight = float(match.group(1))
        if weight >= 8:
            return 12
        if weight >= 2:
            return 4
        return 1
    if "heavy" in text:
        return 10
    if "lightweight" in text:
        return -2
    return 2


def _merge_wall_and_attachment_answer(
    *,
    previous_answers: dict[str, Any],
    wall_material: Any | None,
    attachment_method: Any | None,
) -> str:
    existing = _find_previous_answer(
        previous_answers,
        ("wall", "material", "drill", "adhesive", "hook"),
    )
    existing_text = str(existing or "")
    wall = str(wall_material or _extract_wall_material(_normalize(existing_text)) or "wall material not specified")
    method = str(
        attachment_method
        or (_extract_attachment_update(_normalize(existing_text)) or {}).get("new_value")
        or "attachment method not specified"
    )
    return f"{wall}, {method}"


def _find_previous_answer(
    previous_answers: dict[str, Any],
    keywords: tuple[str, ...],
) -> Any | None:
    for question, answer in previous_answers.items():
        searchable = _normalize(f"{question} {answer}")
        if any(keyword in searchable for keyword in keywords):
            return answer
    return None


def _weight_question_for_intent(task_intent: str) -> str:
    if task_intent == "hanging_wall_decor":
        return "How heavy is the painting and what are its approximate dimensions?"
    return "What is the updated weight or load involved in this task?"


def _wall_method_question_for_intent(task_intent: str) -> str:
    if task_intent == "hanging_wall_decor":
        return "What material is the bedroom wall made of, and will you drill or use adhesive hooks?"
    return "What surface material and attachment method are involved?"


def _append_context_once(task_description: str, addition: str) -> str:
    if _normalize(addition) in _normalize(task_description):
        return task_description
    return f"{task_description} {addition}"


def _first_update_value(
    detected_updates: list[dict[str, Any]],
    fields: set[str],
) -> Any | None:
    for update in detected_updates:
        if update.get("field") in fields:
            return update.get("new_value")
    return None


def _normalize_task_intent(value: str) -> str:
    valid = {
        "hanging_wall_decor",
        "wall_painting",
        "electrical_fixture_installation",
        "electrical_wiring_repair",
        "plumbing_leak_repair",
        "wall_demolition",
        "tile_installation",
        "furniture_assembly",
        "shelf_installation",
        "light_bulb_replacement",
        "ceiling_fan_installation",
        "hvac_repair",
        "general_diy",
    }
    normalized = _normalize(str(value))
    return normalized if normalized in valid else "general_diy"


def _normalize_category_key(value: str, task_intent: str) -> str:
    normalized = _normalize(str(value)).replace(" / ", "_").replace("/", "_").replace(" ", "_")
    label_map = {
        "carpentry_assembly": "carpentry",
        "masonry_demolition": "masonry_demolition",
        "general_diy": "general",
    }
    valid = {
        "electrical",
        "plumbing",
        "masonry_demolition",
        "painting",
        "carpentry",
        "tiling",
        "hvac",
        "roofing",
        "gas",
        "structural",
        "general",
    }
    candidate = label_map.get(normalized, normalized)
    if candidate in valid:
        return candidate
    return category_for_intent(task_intent) or "general"


def _normalize_skill_level(value: Any) -> str:
    normalized = _normalize(str(value or "beginner"))
    return normalized if normalized in {"beginner", "intermediate", "expert"} else "beginner"


def _normalize_location_type(value: Any) -> str:
    normalized = _normalize(str(value or "house"))
    return normalized if normalized in {"house", "apartment", "shop", "office"} else "house"


def _normalize_urgency(value: Any) -> str:
    normalized = _normalize(str(value or "low"))
    return normalized if normalized in {"low", "medium", "high", "emergency"} else "low"


def _normalize_risk_level(value: Any) -> str:
    candidate = _clean_sentence(value)
    return candidate if candidate in RISK_LEVEL_RANK else "Safe DIY"


def _values_differ(old_value: Any, new_value: Any) -> bool:
    if isinstance(old_value, list) or isinstance(new_value, list):
        return _normalize_list_for_compare(old_value) != _normalize_list_for_compare(new_value)
    return _normalize(str(old_value or "")) != _normalize(str(new_value or ""))


def _normalize_list_for_compare(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(_normalize(str(item)) for item in value)


def _risk_score_change_reason(
    detected_updates: list[dict[str, Any]],
    old_score: int | None,
    new_score: int | None,
) -> str:
    if old_score == new_score:
        return "The detected update did not change the numeric risk score."
    if any(update.get("field") in {"painting_weight", "item_weight"} for update in detected_updates):
        return "The item is heavier or the supported load changed, so fixing strength and mounting risk were reassessed."
    if any(update.get("field") == "wall_material" for update in detected_updates):
        return "The wall material changed, so fixing compatibility, drilling effort, and wall failure risk were reassessed."
    if any(update.get("field") == "attachment_method" for update in detected_updates):
        return "The attachment method changed, so drilling hazards and fixing capacity were reassessed."
    if any(update.get("field") == "hidden_utilities" for update in detected_updates):
        return "Possible hidden utilities increase the consequence of drilling, cutting, or opening the wall."
    if any(update.get("field") == "electrical_damage" for update in detected_updates):
        return "Exposed wires or damaged electrical parts substantially increase electrical safety risk."
    return "The updated context changed one or more risk inputs."


def _risk_level_change_reason(
    detected_updates: list[dict[str, Any]],
    old_level: str,
    new_level: str,
) -> str:
    if old_level == new_level:
        return "The update affected assessment details but did not cross a risk-level threshold."
    if any(update.get("field") == "hidden_utilities" for update in detected_updates):
        return "Possible hidden utilities can require professional checking before drilling or cutting."
    if any(update.get("field") == "electrical_damage" for update in detected_updates):
        return "Exposed wires or damaged electrical parts require professional handling."
    if any(update.get("field") in {"painting_weight", "item_weight"} for update in detected_updates):
        return "The updated weight increases mounting failure risk enough to move tiers."
    return "The updated context crossed a risk-level threshold."


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _risk_rank(risk_level: str) -> int:
    return RISK_LEVEL_RANK.get(risk_level, 1)


def _score_to_level(score: int | None) -> str:
    if score is None:
        return "Safe DIY"
    if score >= 81:
        return "Dangerous / permit-required / do not attempt"
    if score >= 61:
        return "Professional required"
    if score >= 41:
        return "Professional recommended"
    if score >= 21:
        return "DIY with supervision"
    return "Safe DIY"


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value is None:
        return []
    return [str(value)]


def _unique_strings(values: list[Any]) -> list[str]:
    cleaned = [_clean_sentence(value) for value in values if _clean_sentence(value)]
    return list(dict.fromkeys(cleaned))


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _parse_with_gemini(
    *,
    previous_assessment: dict[str, Any],
    task_description: str,
    task_intent: str,
    task_category: str,
    previous_answers: dict[str, Any],
    update_message: str,
    current_user_context: dict[str, Any],
    gemini_model: str,
) -> tuple[AssessmentUpdateParseResult | None, dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None, {
            "gemini_error": "GEMINI_API_KEY is missing while GEMINI_ENABLED is true.",
        }

    prompt = _build_gemini_prompt(
        previous_assessment=previous_assessment,
        task_description=task_description,
        task_intent=task_intent,
        task_category=task_category,
        previous_answers=previous_answers,
        update_message=update_message,
        current_user_context=current_user_context,
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "topP": 0.8,
            "responseMimeType": "application/json",
        },
    }

    try:
        with httpx.Client(timeout=12.0) as client:
            response = client.post(
                GEMINI_API_URL.format(model=gemini_model),
                headers={
                    "Content-Type": "application/json",
                    "X-goog-api-key": api_key,
                },
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return None, {"gemini_error": _clean_sentence(str(exc))}

    raw_text = _extract_text(response.json())
    if not raw_text:
        return None, {"gemini_error": "Gemini returned an empty response body."}

    try:
        parsed = json.loads(_strip_json_fences(raw_text))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return None, {
            "gemini_error": f"Gemini response parsing failed: {_clean_sentence(str(exc))}",
        }

    if not isinstance(parsed, dict):
        return None, {"gemini_error": "Gemini JSON response was not an object."}

    result = _normalize_parse_payload(
        parsed,
        previous_assessment=previous_assessment,
        previous_answers=previous_answers,
        current_user_context=current_user_context,
        update_message=update_message,
        gemini_enabled=True,
        gemini_model=gemini_model,
    )
    return result, {}


def _build_gemini_prompt(
    *,
    previous_assessment: dict[str, Any],
    task_description: str,
    task_intent: str,
    task_category: str,
    previous_answers: dict[str, Any],
    update_message: str,
    current_user_context: dict[str, Any],
) -> str:
    previous_assessment_json = json.dumps(previous_assessment, ensure_ascii=True)
    previous_answers_json = json.dumps(previous_answers, ensure_ascii=True)
    context_json = json.dumps(current_user_context, ensure_ascii=True)
    return (
        "You are an update parser inside BuildSafe AI, a safety-first DIY and construction "
        "risk assessment platform.\n"
        "Extract changed information from the user's latest update only.\n"
        "Do not recalculate risk and do not provide DIY instructions.\n\n"
        "Return ONLY valid JSON with this exact shape:\n"
        "{\n"
        '  "is_update_to_existing_assessment": true,\n'
        '  "detected_updates": [\n'
        "    {\n"
        '      "field": "painting_weight",\n'
        '      "old_value_if_known": "1 kg",\n'
        '      "new_value": "2 kg",\n'
        '      "confidence": 0.95\n'
        "    }\n"
        "  ],\n"
        '  "affected_sections": ["risk_score", "materials", "safety_warnings"],\n'
        '  "likely_unchanged_sections": ["task_intent", "task_category", "basic_tools"],\n'
        '  "needs_reassessment": true,\n'
        '  "requires_more_information": false,\n'
        '  "follow_up_questions": [],\n'
        '  "short_reason": "The painting is heavier than previously stated, so anchor strength and mounting risk should be reassessed."\n'
        "}\n\n"
        "Rules:\n"
        "- Extract changed information only.\n"
        "- Do not reinterpret the whole task unless the user clearly changed the task.\n"
        "- Preserve task_intent unless the update changes the task itself.\n"
        "- Identify affected and unaffected sections.\n"
        "- If ambiguous, ask only one clarifying question.\n"
        "- Return valid JSON only. Do not wrap it in markdown.\n\n"
        f"Original task description:\n{task_description}\n\n"
        f"Task intent:\n{task_intent}\n\n"
        f"Task category:\n{task_category}\n\n"
        f"Previous assessment JSON:\n{previous_assessment_json}\n\n"
        f"Previous answers JSON:\n{previous_answers_json}\n\n"
        f"Current user context JSON:\n{context_json}\n\n"
        f"User update message:\n{update_message}"
    )


def _normalize_parse_payload(
    parsed: dict[str, Any],
    *,
    previous_assessment: dict[str, Any],
    previous_answers: dict[str, Any],
    current_user_context: dict[str, Any],
    update_message: str,
    gemini_enabled: bool,
    gemini_model: str,
) -> AssessmentUpdateParseResult:
    detected_updates = _normalize_detected_updates(
        parsed.get("detected_updates"),
        previous_assessment=previous_assessment,
        previous_answers=previous_answers,
        current_user_context=current_user_context,
    )
    affected_sections = _normalize_sections(parsed.get("affected_sections"))
    affected_sections = list(
        dict.fromkeys([*affected_sections, *_sections_for_updates(detected_updates)])
    )

    likely_unchanged_sections = _normalize_sections(parsed.get("likely_unchanged_sections"))
    if not likely_unchanged_sections:
        likely_unchanged_sections = _likely_unchanged_sections(affected_sections)
    else:
        likely_unchanged_sections = [
            section for section in likely_unchanged_sections if section not in affected_sections
        ]

    requires_more_information = bool(parsed.get("requires_more_information", False))
    follow_up_questions = _normalize_list(parsed.get("follow_up_questions"))[:1]
    short_reason = _clean_sentence(parsed.get("short_reason"))
    if not short_reason:
        short_reason = _build_short_reason(detected_updates, requires_more_information)

    return AssessmentUpdateParseResult(
        detected_updates=detected_updates,
        affected_sections=affected_sections,
        likely_unchanged_sections=likely_unchanged_sections,
        needs_reassessment=bool(parsed.get("needs_reassessment", bool(detected_updates))),
        requires_more_information=requires_more_information,
        follow_up_questions=follow_up_questions,
        short_reason=short_reason,
        gemini_enabled=gemini_enabled,
        gemini_used=True,
        fallback_used=False,
        parser_source="gemini",
        gemini_model=gemini_model,
    )


def _parse_with_fallback(
    *,
    previous_assessment: dict[str, Any],
    task_intent: str,
    previous_answers: dict[str, Any],
    update_message: str,
    current_user_context: dict[str, Any],
    gemini_enabled: bool,
    gemini_model: str,
    gemini_error: str | None,
) -> AssessmentUpdateParseResult:
    message = _normalize(update_message)
    detected_updates: list[dict[str, Any]] = []

    weight = _extract_weight_update(message)
    if weight is not None:
        field = "painting_weight" if task_intent == "hanging_wall_decor" else "item_weight"
        _append_update(
            detected_updates,
            field=field,
            old_value_if_known=_lookup_old_value(
                field,
                previous_assessment,
                previous_answers,
                current_user_context,
            ),
            new_value=weight,
            confidence=0.92 if re.search(r"\d", weight) else 0.78,
        )

    wall_material = _extract_wall_material(message)
    if wall_material is not None:
        _append_update(
            detected_updates,
            field="wall_material",
            old_value_if_known=_lookup_old_value(
                "wall_material",
                previous_assessment,
                previous_answers,
                current_user_context,
            ),
            new_value=wall_material,
            confidence=0.9,
        )

    attachment_update = _extract_attachment_update(message)
    if attachment_update is not None:
        _append_update(
            detected_updates,
            field="attachment_method",
            old_value_if_known=attachment_update.get("old_value_if_known")
            or _lookup_old_value(
                "attachment_method",
                previous_assessment,
                previous_answers,
                current_user_context,
            ),
            new_value=attachment_update["new_value"],
            confidence=attachment_update["confidence"],
        )

    hidden_utilities = _extract_hidden_utilities(message)
    if hidden_utilities:
        _append_update(
            detected_updates,
            field="hidden_utilities",
            old_value_if_known=_lookup_old_value(
                "hidden_utilities",
                previous_assessment,
                previous_answers,
                current_user_context,
            ),
            new_value=hidden_utilities,
            confidence=0.82,
        )

    tools_update = _extract_tools_update(message)
    for field, tools in tools_update.items():
        if tools:
            _append_update(
                detected_updates,
                field=field,
                old_value_if_known=_lookup_old_value(
                    field,
                    previous_assessment,
                    previous_answers,
                    current_user_context,
                ),
                new_value=tools,
                confidence=0.82,
            )

    skill_level = _extract_skill_level(message)
    if skill_level is not None:
        _append_update(
            detected_updates,
            field="user_skill_level",
            old_value_if_known=_lookup_old_value(
                "user_skill_level",
                previous_assessment,
                previous_answers,
                current_user_context,
            ),
            new_value=skill_level,
            confidence=0.9,
        )

    electrical_damage = _extract_electrical_damage(message)
    if electrical_damage:
        _append_update(
            detected_updates,
            field="electrical_damage",
            old_value_if_known=_lookup_old_value(
                "electrical_damage",
                previous_assessment,
                previous_answers,
                current_user_context,
            ),
            new_value=electrical_damage,
            confidence=0.9,
        )

    affected_sections = _sections_for_updates(detected_updates)
    likely_unchanged_sections = _likely_unchanged_sections(affected_sections)
    requires_more_information, follow_up_questions = _fallback_clarification(message, detected_updates)

    return AssessmentUpdateParseResult(
        detected_updates=detected_updates,
        affected_sections=affected_sections,
        likely_unchanged_sections=likely_unchanged_sections,
        needs_reassessment=bool(detected_updates),
        requires_more_information=requires_more_information,
        follow_up_questions=follow_up_questions,
        short_reason=_build_short_reason(detected_updates, requires_more_information),
        gemini_enabled=gemini_enabled,
        gemini_used=False,
        fallback_used=True,
        parser_source="fallback",
        gemini_model=gemini_model,
        gemini_error=gemini_error,
    )


def _extract_weight_update(message: str) -> str | None:
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(kg|kgs|kilogram|kilograms)\b", message)
    if match:
        number = float(match.group(1))
        formatted = str(int(number)) if number.is_integer() else str(number)
        return f"{formatted} kg"
    if re.search(r"\blight\s*weight\b|\blightweight\b", message):
        return "lightweight"
    if re.search(r"\bheavy\b", message):
        return "heavy"
    return None


def _extract_wall_material(message: str) -> str | None:
    material_patterns = [
        ("tiled wall", (r"\btiled wall\b", r"\btile wall\b", r"\btiled\b")),
        ("wooden wall", (r"\bwooden wall\b", r"\bwood wall\b", r"\btimber wall\b")),
        ("concrete", (r"\bconcrete\b",)),
        ("brick", (r"\bbrick\b",)),
        ("drywall", (r"\bdrywall\b", r"\bgypsum board\b",)),
        ("plaster", (r"\bplaster\b",)),
    ]
    for label, patterns in material_patterns:
        if any(re.search(pattern, message) for pattern in patterns):
            return label
    return None


def _extract_attachment_update(message: str) -> dict[str, Any] | None:
    method_patterns = [
        ("adhesive strips", (r"\badhesive strips?\b", r"\bcommand strips?\b")),
        ("adhesive hooks", (r"\badhesive hooks?\b",)),
        ("hooks", (r"\bhooks?\b",)),
        ("anchors", (r"\banchors?\b", r"\bwall plugs?\b")),
        ("screws", (r"\bscrews?\b",)),
        ("drilling", (r"\bdrilling\b", r"\bdrill\b")),
    ]
    detected_methods: list[str] = []
    for label, patterns in method_patterns:
        if any(re.search(pattern, message) for pattern in patterns):
            detected_methods.append(label)

    if not detected_methods:
        return None

    old_method = None
    if re.search(r"\b(instead of|rather than|not)\s+drilling\b", message):
        old_method = "drilling"
    elif re.search(r"\bwithout\s+(a\s+)?drill\b", message):
        old_method = "drilling"

    new_candidates = [method for method in detected_methods if method != old_method]
    new_value = new_candidates[0] if new_candidates else detected_methods[0]
    return {
        "old_value_if_known": old_method,
        "new_value": new_value,
        "confidence": 0.88 if old_method else 0.82,
    }


def _extract_hidden_utilities(message: str) -> list[str]:
    hidden_context = re.search(r"\b(behind|inside|within|hidden|wall|ceiling|floor)\b", message)
    if not hidden_context:
        return []

    return _utility_values_from_text(message)


def _utility_values_from_text(text: str) -> list[str]:
    message = _normalize(text)

    utilities: list[str] = []
    if re.search(r"\bwiring\b|\belectrical wires?\b|\bwires?\b", message):
        utilities.append("wiring")
    if re.search(r"\bpipes?\b|\bplumbing\b", message):
        utilities.append("plumbing/pipes")
    if re.search(r"\bgas line\b|\bgas pipe\b|\bgas\b", message):
        utilities.append("gas line")
    return list(dict.fromkeys(utilities))


def _extract_tools_update(message: str) -> dict[str, list[str]]:
    tools = {
        "drill": (r"\bdrill\b",),
        "ladder": (r"\bladder\b",),
        "voltage tester": (r"\bvoltage tester\b", r"\btester\b"),
        "PPE": (r"\bppe\b", r"\bgoggles?\b", r"\bgloves?\b", r"\bmask\b", r"\brespirator\b", r"\bhelmet\b"),
    }
    available: list[str] = []
    unavailable: list[str] = []

    for label, patterns in tools.items():
        match = next((re.search(pattern, message) for pattern in patterns if re.search(pattern, message)), None)
        if match is None:
            continue
        nearby_text = message[max(0, match.start() - 35): match.end() + 35]
        if re.search(r"\b(don't|dont|do not|no|without|lack|missing)\b", nearby_text):
            unavailable.append(label)
        else:
            available.append(label)

    return {
        "available_tools": list(dict.fromkeys(available)),
        "unavailable_tools": list(dict.fromkeys(unavailable)),
    }


def _extract_skill_level(message: str) -> str | None:
    match = re.search(r"\b(beginner|intermediate|expert)\b", message)
    if match:
        return match.group(1)
    return None


def _extract_electrical_damage(message: str) -> list[str]:
    signals: list[str] = []
    if re.search(r"\bexposed wires?\b|\bcan see wires?\b|\bvisible wires?\b", message):
        signals.append("exposed wires")
    if re.search(
        r"\bdamaged holder\b|\bholder is damaged\b|\bbroken holder\b|\bdamaged fitting\b|\bfitting is damaged\b",
        message,
    ):
        signals.append("damaged holder")
    if re.search(r"\bbroken socket\b|\bdamaged socket\b", message):
        signals.append("broken socket")
    return list(dict.fromkeys(signals))


def _append_update(
    updates: list[dict[str, Any]],
    *,
    field: str,
    old_value_if_known: Any | None,
    new_value: Any,
    confidence: float,
) -> None:
    if any(update["field"] == field and update["new_value"] == new_value for update in updates):
        return
    updates.append(
        {
            "field": field,
            "old_value_if_known": old_value_if_known,
            "new_value": new_value,
            "confidence": round(max(0.0, min(1.0, confidence)), 2),
        }
    )


def _lookup_old_value(
    field: str,
    previous_assessment: dict[str, Any],
    previous_answers: dict[str, Any],
    current_user_context: dict[str, Any],
) -> Any | None:
    if field == "user_skill_level":
        return current_user_context.get("user_skill_level")
    if field in {"available_tools", "unavailable_tools"}:
        return current_user_context.get("available_tools")

    keyword_map = {
        "painting_weight": ("weight", "heavy", "lightweight", "kg", "kilogram"),
        "item_weight": ("weight", "heavy", "lightweight", "kg", "kilogram"),
        "wall_material": ("wall", "material", "concrete", "brick", "drywall", "plaster", "tile", "wood"),
        "attachment_method": ("drill", "adhesive", "hook", "anchor", "screw"),
        "hidden_utilities": ("wiring", "wire", "pipe", "plumbing", "gas", "utility"),
        "electrical_damage": ("wire", "holder", "socket", "fitting", "damaged", "broken"),
    }
    keywords = keyword_map.get(field, ())
    for key, value in previous_answers.items():
        searchable = f"{key} {value}".lower()
        if any(keyword in searchable for keyword in keywords):
            return value

    previous_text = json.dumps(previous_assessment, ensure_ascii=True).lower()
    if any(keyword in previous_text for keyword in keywords):
        return None
    return None


def _normalize_detected_updates(
    value: Any,
    *,
    previous_assessment: dict[str, Any],
    previous_answers: dict[str, Any],
    current_user_context: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    updates: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        field = _normalize_update_field(item.get("field"), item.get("new_value"))
        if not field or "new_value" not in item:
            continue
        new_value = _normalize_update_value(field, item["new_value"])
        old_value = item.get("old_value_if_known")
        if old_value in {"", "unknown", "Unknown", "not known"}:
            old_value = None
        if old_value is None:
            old_value = _lookup_old_value(
                field,
                previous_assessment,
                previous_answers,
                current_user_context,
            )
        try:
            confidence = float(item.get("confidence", 0.8))
        except (TypeError, ValueError):
            confidence = 0.8
        _append_update(
            updates,
            field=field,
            old_value_if_known=old_value,
            new_value=new_value,
            confidence=confidence,
        )
    return updates


def _normalize_update_field(raw_field: Any, new_value: Any) -> str:
    field = _normalize(str(raw_field)).replace(" ", "_")
    value_text = _normalize(str(new_value))

    if not field:
        return ""
    if _utility_values_from_text(value_text):
        return "hidden_utilities"
    if "weight" in field:
        return "painting_weight"
    if field in {"mounting_method", "fixing_method", "fixing_type", "attachment", "attachment_type"}:
        return "attachment_method"
    if "adhesive" in field or "drill" in field or "anchor" in field or "screw" in field:
        return "attachment_method"
    if field in {"wall_type", "wall_surface", "wall_material_details"}:
        if _utility_values_from_text(value_text):
            return "hidden_utilities"
        return "wall_material"
    if "wall_material" in field:
        return "wall_material"
    if field in {"hidden_services", "hidden_utility", "hidden_utilities", "behind_wall_services"}:
        return "hidden_utilities"
    if (
        "wiring" in field
        or "plumbing" in field
        or "gas" in field
        or "utilities" in field
        or "hazard" in field
    ):
        return "hidden_utilities"
    if field in {"tools", "tool_availability", "available_tool", "available_tools"}:
        return "available_tools"
    if field in {"missing_tools", "unavailable_tool", "unavailable_tools"}:
        return "unavailable_tools"
    if "skill" in field or "experience" in field:
        return "user_skill_level"
    if "damage" in field or "holder" in field or "socket" in field or "exposed_wire" in field:
        return "electrical_damage"
    return field


def _normalize_update_value(field: str, value: Any) -> Any:
    if field == "hidden_utilities":
        utilities = _utility_values_from_text(str(value))
        return utilities or value
    if field == "attachment_method":
        attachment = _extract_attachment_update(_normalize(str(value)))
        if attachment is not None:
            return attachment["new_value"]
    if field == "wall_material":
        material = _extract_wall_material(_normalize(str(value)))
        if material is not None:
            return material
    if field in {"painting_weight", "item_weight"}:
        weight = _extract_weight_update(_normalize(str(value)))
        if weight is not None:
            return weight
    if field == "electrical_damage":
        if isinstance(value, list):
            return value
        damage = _extract_electrical_damage(_normalize(str(value)))
        return damage or value
    return value


def _sections_for_updates(updates: list[dict[str, Any]]) -> list[str]:
    sections: list[str] = []
    for update in updates:
        sections.extend(SECTION_MAP.get(update["field"], ["risk_score", "safety_warnings"]))
    return list(dict.fromkeys(sections))


def _likely_unchanged_sections(affected_sections: list[str]) -> list[str]:
    affected = set(affected_sections)
    return [section for section in ALL_SECTIONS if section not in affected]


def _fallback_clarification(
    message: str,
    detected_updates: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    if not detected_updates:
        return False, []

    is_uncertain = bool(re.search(r"\b(may|might|maybe|possibly|not sure|unsure|could)\b", message))
    has_hidden_utilities = any(update["field"] == "hidden_utilities" for update in detected_updates)
    if is_uncertain and has_hidden_utilities:
        return True, [
            "Will you need to drill, cut, or open the wall near the suspected wiring, pipes, or gas line?",
        ]

    return False, []


def _build_short_reason(
    detected_updates: list[dict[str, Any]],
    requires_more_information: bool,
) -> str:
    if not detected_updates:
        return "I received the update, but could not detect a structured assessment change yet."

    field_labels = {
        "painting_weight": "weight",
        "item_weight": "weight",
        "wall_material": "wall material",
        "attachment_method": "attachment method",
        "hidden_utilities": "hidden utilities",
        "available_tools": "tool availability",
        "unavailable_tools": "tool availability",
        "user_skill_level": "skill level",
        "electrical_damage": "electrical damage",
    }
    labels = [field_labels.get(update["field"], update["field"]) for update in detected_updates]
    unique_labels = list(dict.fromkeys(labels))
    reason = f"Detected update to {', '.join(unique_labels)}; the affected assessment sections should be reviewed."
    if requires_more_information:
        reason += " One clarification is needed before reassessment."
    return reason


def _normalize_sections(value: Any) -> list[str]:
    sections = [_normalize_section_name(section) for section in _normalize_list(value)]
    return [section for section in list(dict.fromkeys(sections)) if section]


def _normalize_section_name(value: str) -> str:
    normalized = _normalize(value).replace(" ", "_")
    section_map = {
        "required_tools": "basic_tools",
        "tools": "basic_tools",
        "basic_tools": "basic_tools",
        "required_materials": "materials",
        "materials": "materials",
        "required_ppe": "ppe",
        "ppe": "ppe",
        "recommended_professional_category": "professional_recommendation",
        "professional": "professional_recommendation",
        "professional_recommendation": "professional_recommendation",
        "estimated_time": "estimated_time",
        "safety_warnings": "safety_warnings",
        "risk_score": "risk_score",
        "risk_level": "risk_level",
        "task_intent": "task_intent",
        "task_category": "task_category",
        "action_plan": "action_plan",
    }
    return section_map.get(normalized, normalized if normalized in ALL_SECTIONS else "")


def _normalize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        cleaned = _clean_sentence(item)
        if cleaned:
            normalized.append(cleaned)
    return list(dict.fromkeys(normalized))


def _extract_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates", [])
    if not candidates:
        return ""

    parts = candidates[0].get("content", {}).get("parts", [])
    text_parts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    return "\n".join(part for part in text_parts if part).strip()


def _strip_json_fences(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    return stripped


def _gemini_enabled() -> bool:
    return os.getenv("GEMINI_ENABLED", "false").strip().lower() == "true"


def _gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


def _clean_sentence(value: Any) -> str:
    return " ".join(str(value).strip().split())


def _normalize(value: str) -> str:
    return " ".join(value.lower().strip().split())
