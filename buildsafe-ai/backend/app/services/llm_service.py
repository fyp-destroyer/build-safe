from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx
from dotenv import load_dotenv

from app.models import CATEGORY_PROFILES, MIN_SCORE_BY_LEVEL
from app.schemas import DebugTrace, FollowupPlanResponse, RiskLevel, TaskIntent
from app.services.task_intent_service import category_for_intent, detect_task_intent

load_dotenv()
logger = logging.getLogger(__name__)

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
RISK_LEVEL_TO_SCORE: dict[RiskLevel, int] = {
    "Safe DIY": MIN_SCORE_BY_LEVEL[1],
    "DIY with supervision": MIN_SCORE_BY_LEVEL[2],
    "Professional recommended": MIN_SCORE_BY_LEVEL[3],
    "Professional required": MIN_SCORE_BY_LEVEL[4],
    "Dangerous / permit-required / do not attempt": MIN_SCORE_BY_LEVEL[5],
}


def plan_followups(
    task_description: str,
    known_answers: dict[str, Any] | None = None,
) -> FollowupPlanResponse:
    answers = known_answers or {}
    gemini_enabled = _gemini_enabled()
    gemini_model = _gemini_model()

    if gemini_enabled:
        logger.info("Gemini follow-up planning attempt started. model=%s", gemini_model)
        llm_plan, gemini_trace = _plan_followups_with_gemini(task_description, answers)
        if llm_plan is not None:
            logger.info("Gemini follow-up planning succeeded. model=%s", gemini_model)
            return _attach_debug_trace(
                llm_plan,
                _build_plan_debug_trace(
                    response=llm_plan,
                    gemini_enabled=gemini_enabled,
                    gemini_used=True,
                    gemini_model=gemini_model,
                    gemini_used_for=["task_intent_detection", "followup_planning"],
                    fallback_used=False,
                    notes=[
                        "Gemini parsed the task intent and chose the follow-up questions.",
                    ],
                    parsed_llm_response=gemini_trace.get("parsed_llm_response"),
                    llm_response_text=gemini_trace.get("llm_response_text"),
                    llm_prompt=gemini_trace.get("llm_prompt"),
                ),
            )

        logger.warning(
            "Gemini follow-up planning failed. model=%s reason=%s",
            gemini_model,
            gemini_trace.get("gemini_error") or "unknown",
        )
        logger.info("Using deterministic follow-up fallback after Gemini failure.")
        fallback_plan = _build_fallback_plan(task_description, answers, llm_used=False)
        return _attach_debug_trace(
            fallback_plan,
            _build_plan_debug_trace(
                response=fallback_plan,
                gemini_enabled=gemini_enabled,
                gemini_used=False,
                gemini_model=gemini_model,
                gemini_used_for=[],
                fallback_used=True,
                notes=[
                    "Gemini failed during follow-up planning, so the deterministic fallback planner was used.",
                ],
                gemini_error=gemini_trace.get("gemini_error"),
                parsed_llm_response=gemini_trace.get("parsed_llm_response"),
                llm_response_text=gemini_trace.get("llm_response_text"),
                llm_prompt=gemini_trace.get("llm_prompt"),
            ),
        )

    logger.info("Gemini skipped for follow-up planning. GEMINI_ENABLED=%s", gemini_enabled)
    fallback_note = (
        "Gemini is disabled in backend configuration."
        if not gemini_enabled
        else "Gemini was not used."
    )
    fallback_plan = _build_fallback_plan(task_description, answers, llm_used=False)
    return _attach_debug_trace(
        fallback_plan,
        _build_plan_debug_trace(
            response=fallback_plan,
            gemini_enabled=gemini_enabled,
            gemini_used=False,
            gemini_model=gemini_model,
            gemini_used_for=[],
            fallback_used=True,
            notes=[fallback_note],
        ),
    )


def suggested_risk_score(risk_level: RiskLevel) -> int:
    return RISK_LEVEL_TO_SCORE[risk_level]


def _plan_followups_with_gemini(
    task_description: str,
    known_answers: dict[str, Any],
) -> tuple[FollowupPlanResponse | None, dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = _gemini_model()

    if not api_key:
        return None, {
            "gemini_error": "GEMINI_API_KEY is missing while GEMINI_ENABLED is true.",
        }

    prompt = _build_prompt(task_description, known_answers)
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt,
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.8,
            "responseMimeType": "application/json",
        },
    }

    try:
        with httpx.Client(timeout=12.0) as client:
            response = client.post(
                GEMINI_API_URL.format(model=model),
                headers={
                    "Content-Type": "application/json",
                    "X-goog-api-key": api_key,
                },
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return None, {
            "gemini_error": _clean_sentence(str(exc)),
            "llm_prompt": prompt,
        }

    raw_text = _extract_text(response.json())
    if not raw_text:
        return None, {
            "gemini_error": "Gemini returned an empty response body.",
            "llm_prompt": prompt,
        }

    try:
        parsed = json.loads(_strip_json_fences(raw_text))
        follow_up_questions = _normalize_list(parsed.get("follow_up_questions"))[:2]
        critical_missing_info = _normalize_list(parsed.get("critical_missing_info"))
        risk_factors = _normalize_list(parsed.get("risk_factors"))
        task_intent = _normalize_task_intent(parsed.get("task_intent"))
        task_category = _normalize_category(parsed.get("task_category"))
        is_ambiguous = bool(parsed.get("is_ambiguous", False))
        possible_interpretations = _normalize_list(parsed.get("possible_interpretations"))
        selected_interpretation = _clean_sentence(parsed.get("selected_interpretation"))
        suggested_risk_level = _normalize_risk_level(parsed.get("suggested_risk_level"))
        short_reason = _clean_sentence(parsed.get("short_reason"))

        if not task_intent or not suggested_risk_level or not short_reason:
            return None, {
                "gemini_error": "Gemini JSON response was missing one or more required fields.",
                "parsed_llm_response": parsed if isinstance(parsed, dict) else None,
                "llm_response_text": _trim_debug_text(raw_text),
                "llm_prompt": prompt,
            }

        if task_category == "general":
            task_category = category_for_intent(task_intent)

        plan = FollowupPlanResponse(
            task_intent=task_intent,
            task_category=task_category,
            is_ambiguous=is_ambiguous,
            possible_interpretations=possible_interpretations[:3],
            selected_interpretation=selected_interpretation,
            risk_factors=risk_factors,
            critical_missing_info=critical_missing_info[:3],
            follow_up_questions=follow_up_questions,
            suggested_risk_level=suggested_risk_level,
            short_reason=short_reason,
            llm_used=True,
        )
        return plan, {
            "parsed_llm_response": parsed if isinstance(parsed, dict) else None,
            "llm_response_text": _trim_debug_text(raw_text),
            "llm_prompt": prompt,
        }
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return None, {
            "gemini_error": f"Gemini response parsing failed: {_clean_sentence(str(exc))}",
            "llm_response_text": _trim_debug_text(raw_text),
            "llm_prompt": prompt,
        }


def _build_prompt(task_description: str, known_answers: dict[str, Any]) -> str:
    serialized_answers = json.dumps(known_answers, ensure_ascii=True)
    return (
        "You are an AI assistant inside BuildSafe AI, a safety-first DIY and construction "
        "task triage platform.\n"
        "Your job is not to give step-by-step DIY instructions.\n"
        "Your job is to analyze the user's task, determine the real task intent, and decide "
        "which information is crucial for risk assessment.\n\n"
        "Return ONLY valid JSON with this shape:\n"
        "{\n"
        '  "task_intent": "hanging_wall_decor | wall_painting | electrical_fixture_installation | '
        'electrical_wiring_repair | plumbing_leak_repair | wall_demolition | tile_installation | '
        'furniture_assembly | shelf_installation | light_bulb_replacement | ceiling_fan_installation | '
        'hvac_repair | general_diy",\n'
        '  "task_category": "electrical | plumbing | masonry_demolition | painting | carpentry | '
        'tiling | hvac | roofing | general",\n'
        '  "is_ambiguous": false,\n'
        '  "possible_interpretations": [],\n'
        '  "selected_interpretation": "brief interpretation",\n'
        '  "risk_factors": ["..."],\n'
        '  "critical_missing_info": ["..."],\n'
        '  "follow_up_questions": ["question 1", "question 2"],\n'
        '  "suggested_risk_level": "Safe DIY | DIY with supervision | Professional recommended | '
        'Professional required | Dangerous / permit-required / do not attempt",\n'
        '  "short_reason": "brief explanation"\n'
        "}\n\n"
        "Rules:\n"
        "- Determine the action verb and object before choosing the task intent.\n"
        '- "hang a painting", "hang artwork", or "mount a frame" means hanging wall decor, not painting a room.\n'
        '- "paint my bedroom", "paint the walls", or "apply paint" means wall painting.\n'
        "- Ask maximum 2 follow-up questions.\n"
        "- Do not ask about budget unless budget is genuinely needed for the task decision.\n"
        "- Do not ask unnecessary questions for simple tasks.\n"
        "- If the task involves electrical wiring, gas, structural demolition, roof work, main "
        "plumbing lines, or unknown load-bearing walls, be conservative.\n"
        "- For dangerous tasks, do not provide step-by-step instructions.\n"
        "- If information is missing and the missing information affects safety, list it in "
        "critical_missing_info.\n"
        "- Keep the output concise.\n\n"
        f"User task:\n{task_description}\n\n"
        f"Existing known user answers:\n{serialized_answers}"
    )


def _build_fallback_plan(
    task_description: str,
    known_answers: dict[str, Any],
    *,
    llm_used: bool,
) -> FollowupPlanResponse:
    task_text = _normalize(task_description)
    answers_index = _answers_index(known_answers)
    intent_result = detect_task_intent(task_description)

    if intent_result.task_intent == "hanging_wall_decor":
        return _plan_hanging_wall_decor(task_description, answers_index, llm_used, intent_result)
    if intent_result.task_intent == "light_bulb_replacement":
        return _plan_light_bulb(task_description, answers_index, llm_used)
    if intent_result.task_intent == "ceiling_fan_installation":
        return _plan_ceiling_fan(task_description, answers_index, llm_used)
    if intent_result.task_intent == "wall_demolition":
        return _plan_wall_demolition(task_description, answers_index, llm_used)
    if intent_result.task_intent == "plumbing_leak_repair":
        return _plan_pipe_leak(task_description, answers_index, llm_used)
    if intent_result.task_intent == "wall_painting":
        return _plan_painting(task_description, answers_index, llm_used)

    category_key = intent_result.task_category
    if category_key == "general":
        category_key = _detect_category(task_text)
    generic_questions = _default_questions_for_category(category_key)
    unresolved_questions = _unanswered_questions(generic_questions, answers_index)
    risk_level = _default_risk_for_category(category_key)

    return FollowupPlanResponse(
        task_intent=intent_result.task_intent,
        task_category=category_key,
        is_ambiguous=intent_result.is_ambiguous,
        possible_interpretations=intent_result.possible_interpretations,
        selected_interpretation=intent_result.selected_interpretation,
        risk_factors=_default_risk_factors_for_category(category_key),
        critical_missing_info=[_critical_info_for_question(question) for question in unresolved_questions],
        follow_up_questions=unresolved_questions,
        suggested_risk_level=risk_level,
        short_reason=_default_reason_for_category(category_key, risk_level),
        llm_used=llm_used,
    )


def _plan_hanging_wall_decor(
    task_description: str,
    answers_index: dict[str, str],
    llm_used: bool,
    intent_result: Any,
) -> FollowupPlanResponse:
    questions = [
        "How heavy is the painting and what are its approximate dimensions?",
        "What material is the bedroom wall made of, and will you drill or use adhesive hooks?",
    ]
    unresolved_questions = _unanswered_questions(questions, answers_index)
    suggested_risk = "Safe DIY"
    short_reason = (
        "This is usually a low-risk DIY task unless the item is heavy, drilling is required, "
        "or hidden utilities may be present."
    )

    if _answer_signals_yes(answers_index, ("drill", "wall material", "adhesive hooks")):
        suggested_risk = "DIY with supervision"
    if _answer_signals_yes(answers_index, ("heavy", "dimensions")):
        suggested_risk = "DIY with supervision"

    return FollowupPlanResponse(
        task_intent="hanging_wall_decor",
        task_category="carpentry",
        is_ambiguous=intent_result.is_ambiguous,
        possible_interpretations=intent_result.possible_interpretations,
        selected_interpretation=(
            "The user wants to hang framed artwork on a bedroom wall, not paint the bedroom."
        ),
        risk_factors=[
            "Wall material unknown",
            "Painting weight unknown",
            "Hidden wires or pipes if drilling is required",
        ],
        critical_missing_info=[_critical_info_for_question(question) for question in unresolved_questions],
        follow_up_questions=unresolved_questions,
        suggested_risk_level=suggested_risk,
        short_reason=short_reason,
        llm_used=llm_used,
    )


def _plan_light_bulb(
    task_description: str,
    answers_index: dict[str, str],
    llm_used: bool,
) -> FollowupPlanResponse:
    task_text = _normalize(task_description)
    questions = [
        "Are you only replacing a standard bulb, or does this involve wiring or the light fitting?",
    ]
    if _contains_any(task_text, ("ceiling", "high", "stairs", "ladder")):
        questions.append("Will you be using a ladder or working at height to reach the bulb?")
    unresolved_questions = _unanswered_questions(questions, answers_index)
    suggested_risk = "Safe DIY"
    short_reason = "A standard bulb replacement is usually low risk unless wiring or height access is involved."

    if _answer_signals_yes(answers_index, ("wiring", "light fitting")):
        suggested_risk = "Professional recommended"
        short_reason = "Once wiring or the fitting itself is involved, shock and mounting risks increase."
    elif _answer_signals_yes(answers_index, ("ladder", "height")):
        suggested_risk = "DIY with supervision"
        short_reason = "The task stays relatively simple, but height access raises fall risk."

    return FollowupPlanResponse(
        task_intent="light_bulb_replacement",
        task_category="electrical",
        is_ambiguous=False,
        possible_interpretations=[],
        selected_interpretation="The user wants to replace a light bulb rather than rewire the fitting.",
        risk_factors=["Electrical isolation", "Heat from the existing bulb", "Fall risk if height access is needed"],
        critical_missing_info=[_critical_info_for_question(question) for question in unresolved_questions],
        follow_up_questions=unresolved_questions,
        suggested_risk_level=suggested_risk,
        short_reason=short_reason,
        llm_used=llm_used,
    )


def _plan_ceiling_fan(
    task_description: str,
    answers_index: dict[str, str],
    llm_used: bool,
) -> FollowupPlanResponse:
    questions = [
        "Is there existing wiring and a fan-rated ceiling box already in place?",
        "What is your skill level with electrical work: beginner, intermediate, or expert?",
    ]
    unresolved_questions = _unanswered_questions(questions, answers_index)
    suggested_risk = "Professional recommended"
    short_reason = "Ceiling fan installation mixes electrical work with overhead mounting and support requirements."

    if _answer_is_negative_or_unknown(answers_index, ("fan-rated", "ceiling box", "existing wiring")):
        suggested_risk = "Professional required"
        short_reason = "Unknown or unsuitable wiring and support hardware make this unsafe to treat as a simple DIY task."
    elif _answer_contains(answers_index, ("skill level", "electrical work"), ("beginner",)):
        suggested_risk = "Professional recommended"
        short_reason = "Even with existing wiring, a beginner should treat ceiling-fan wiring and support checks cautiously."

    return FollowupPlanResponse(
        task_intent="ceiling_fan_installation",
        task_category="electrical",
        is_ambiguous=False,
        possible_interpretations=[],
        selected_interpretation="The user wants to install or replace a ceiling fan.",
        risk_factors=["Electrical shock risk", "Fixture support and movement", "Overhead ladder work"],
        critical_missing_info=[_critical_info_for_question(question) for question in unresolved_questions],
        follow_up_questions=unresolved_questions,
        suggested_risk_level=suggested_risk,
        short_reason=short_reason,
        llm_used=llm_used,
    )


def _plan_wall_demolition(
    task_description: str,
    answers_index: dict[str, str],
    llm_used: bool,
) -> FollowupPlanResponse:
    questions = [
        "Do you know whether the wall is load-bearing?",
        "Could there be wiring, plumbing, or gas lines inside the wall?",
    ]
    unresolved_questions = _unanswered_questions(questions, answers_index)
    suggested_risk = "Professional required"
    short_reason = "Wall removal can affect structure and hidden services even before demolition starts."

    if _answer_is_negative_or_unknown(answers_index, ("load-bearing",)):
        suggested_risk = "Dangerous / permit-required / do not attempt"
        short_reason = "If the wall may be load-bearing or that is unknown, the task needs professional structural review."
    elif _answer_signals_yes(answers_index, ("wiring", "plumbing", "gas")):
        suggested_risk = "Professional required"
        short_reason = "Hidden services inside the wall can create shock, flooding, or gas hazards during demolition."

    return FollowupPlanResponse(
        task_intent="wall_demolition",
        task_category="masonry_demolition",
        is_ambiguous=False,
        possible_interpretations=[],
        selected_interpretation="The user wants to remove or break a wall, not do decorative finishing work.",
        risk_factors=["Potential structural load", "Hidden utilities", "Dust and debris hazards"],
        critical_missing_info=[_critical_info_for_question(question) for question in unresolved_questions],
        follow_up_questions=unresolved_questions,
        suggested_risk_level=suggested_risk,
        short_reason=short_reason,
        llm_used=llm_used,
    )


def _plan_pipe_leak(
    task_description: str,
    answers_index: dict[str, str],
    llm_used: bool,
) -> FollowupPlanResponse:
    questions = [
        "Is the leak near electrical outlets, switches, or appliances?",
        "Is this a minor visible joint leak, or a hidden or main line leak?",
    ]
    unresolved_questions = _unanswered_questions(questions, answers_index)
    suggested_risk = "DIY with supervision"
    short_reason = "Small accessible plumbing leaks may be manageable, but hidden leaks can escalate quickly."

    if _answer_signals_yes(answers_index, ("electrical", "outlet", "switch", "appliance")):
        suggested_risk = "Professional required"
        short_reason = "Water near live electrical equipment creates combined shock and property-damage risk."
    elif _answer_signals_yes(answers_index, ("hidden", "main line")):
        suggested_risk = "Professional recommended"
        short_reason = "Hidden or main-line leaks usually need inspection beyond a basic DIY patch."

    return FollowupPlanResponse(
        task_intent="plumbing_leak_repair",
        task_category="plumbing",
        is_ambiguous=False,
        possible_interpretations=[],
        selected_interpretation="The user wants to repair a plumbing leak.",
        risk_factors=["Water damage", "Leak escalation", "Electrical contact if water spreads"],
        critical_missing_info=[_critical_info_for_question(question) for question in unresolved_questions],
        follow_up_questions=unresolved_questions,
        suggested_risk_level=suggested_risk,
        short_reason=short_reason,
        llm_used=llm_used,
    )


def _plan_painting(
    task_description: str,
    answers_index: dict[str, str],
    llm_used: bool,
) -> FollowupPlanResponse:
    questions = [
        "Is there dampness, mold, or peeling paint on the surface?",
        "What is your experience level with this kind of painting work?",
    ]
    unresolved_questions = _unanswered_questions(questions, answers_index)
    suggested_risk = "Safe DIY"
    short_reason = "Basic room painting is usually low risk when the surfaces are sound and the room can be ventilated."

    if _answer_signals_yes(answers_index, ("damp", "mold", "peeling")):
        suggested_risk = "DIY with supervision"
        short_reason = "Moisture damage, mold, or failing paint layers add prep and health risks beyond a simple repaint."

    return FollowupPlanResponse(
        task_intent="wall_painting",
        task_category="painting",
        is_ambiguous=False,
        possible_interpretations=[],
        selected_interpretation="The user wants to apply paint to room surfaces.",
        risk_factors=["Ventilation and fumes", "Surface condition", "Ladder use for edges and ceilings"],
        critical_missing_info=[_critical_info_for_question(question) for question in unresolved_questions],
        follow_up_questions=unresolved_questions,
        suggested_risk_level=suggested_risk,
        short_reason=short_reason,
        llm_used=llm_used,
    )


def _answers_index(known_answers: dict[str, Any]) -> dict[str, str]:
    index: dict[str, str] = {}
    for key, value in known_answers.items():
        index[_normalize(str(key))] = _normalize(str(value))
    return index


def _unanswered_questions(
    questions: list[str],
    answers_index: dict[str, str],
) -> list[str]:
    unanswered: list[str] = []
    for question in questions:
        if _find_answer(answers_index, question) is None:
            unanswered.append(question)
    return unanswered[:2]


def _find_answer(answers_index: dict[str, str], question: str) -> str | None:
    normalized_question = _normalize(question)
    for answer_key, answer_value in answers_index.items():
        if answer_key == normalized_question:
            return answer_value
        if any(token in answer_key for token in _question_tokens(normalized_question)):
            return answer_value
    return None


def _question_tokens(question: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", question) if len(token) > 3]


def _answer_signals_yes(answers_index: dict[str, str], tokens: tuple[str, ...]) -> bool:
    return _answer_contains(answers_index, tokens, ("yes", "wiring", "fitting", "height", "hidden", "main"))


def _answer_is_negative_or_unknown(answers_index: dict[str, str], tokens: tuple[str, ...]) -> bool:
    return _answer_contains(answers_index, tokens, ("no", "not sure", "unknown", "unsure"))


def _answer_contains(
    answers_index: dict[str, str],
    question_tokens: tuple[str, ...],
    answer_tokens: tuple[str, ...],
) -> bool:
    for answer_key, answer_value in answers_index.items():
        if not any(token in answer_key for token in question_tokens):
            continue
        if any(token in answer_value for token in answer_tokens):
            return True
    return False


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


def _default_questions_for_category(category_key: str) -> list[str]:
    question_map = {
        "electrical": [
            "Does this involve exposed wiring, a fitting, or just a simple like-for-like replacement?",
            "What is your skill level with this kind of electrical work?",
        ],
        "plumbing": [
            "Can you isolate the water supply before starting?",
            "Is the leak or pipe issue visible and accessible, or hidden inside a wall, floor, or ceiling?",
        ],
        "masonry_demolition": [
            "Do you know whether the surface or wall is non-load-bearing?",
            "Could there be wiring, plumbing, or gas lines behind it?",
        ],
        "painting": [
            "Is there dampness, mold, or peeling paint that needs repair first?",
            "Will you need ladder work or poor-ventilation work for this task?",
        ],
        "carpentry": [
            "Do you know the wall or surface type and the weight the fixings need to support?",
            "Have you checked for hidden wiring or plumbing before drilling?",
        ],
        "tiling": [
            "Is this in a wet area or somewhere that needs waterproofing?",
            "Will you need to cut tiles or drill near hidden services?",
        ],
        "hvac": [
            "Does this involve refrigerant, hardwired electrical work, or sealed equipment?",
            "Do you have the correct manufacturer guidance for the exact unit or part?",
        ],
        "roofing": [
            "Will you be working at roof height or near an exposed edge?",
            "Is the roof dry and safely accessible with fall protection?",
        ],
    }
    return question_map.get(
        category_key,
        [
            "Are there any hidden utilities, moisture, or access hazards involved?",
            "What part of the task feels most uncertain or safety-sensitive?",
        ],
    )


def _default_risk_for_category(category_key: str) -> RiskLevel:
    if category_key == "painting":
        return "Safe DIY"
    if category_key in {"plumbing", "tiling", "carpentry"}:
        return "DIY with supervision"
    if category_key in {"electrical", "hvac"}:
        return "Professional recommended"
    if category_key in {"roofing", "masonry_demolition"}:
        return "Professional required"
    return "DIY with supervision"


def _default_risk_factors_for_category(category_key: str) -> list[str]:
    risk_map = {
        "electrical": ["Shock risk", "Hidden wiring condition", "Isolation and testing"],
        "plumbing": ["Water spread", "Hidden leak path", "Electrical exposure if water travels"],
        "masonry_demolition": ["Structure", "Hidden utilities", "Dust and debris"],
        "painting": ["Ventilation", "Surface condition", "Ladder use if needed"],
        "carpentry": ["Fixing strength", "Wall type", "Hidden services before drilling"],
        "tiling": ["Surface prep", "Cutting dust", "Waterproofing in wet areas"],
        "hvac": ["Electrical load", "Sealed components", "Manufacturer-specific constraints"],
        "roofing": ["Fall risk", "Weather exposure", "Fragile surfaces"],
    }
    return risk_map.get(category_key, ["Unknown site conditions", "Tool suitability"])


def _default_reason_for_category(category_key: str, risk_level: RiskLevel) -> str:
    label = CATEGORY_PROFILES.get(category_key, CATEGORY_PROFILES["general"]).label
    return f"This looks like a {label.lower()} task, so the MVP is taking a {risk_level.lower()} stance until the main safety unknowns are clarified."


def _critical_info_for_question(question: str) -> str:
    question_map = {
        "How heavy is the painting and what are its approximate dimensions?": "The weight and size of the item being hung",
        "What material is the bedroom wall made of, and will you drill or use adhesive hooks?": "The wall material and attachment method",
        "Are you only replacing a standard bulb, or does this involve wiring or the light fitting?": "Whether the task is a simple bulb swap or electrical fitting work",
        "Will you be using a ladder or working at height to reach the bulb?": "Whether height access is needed",
        "Is there existing wiring and a fan-rated ceiling box already in place?": "Whether safe wiring and rated support already exist",
        "What is your skill level with electrical work: beginner, intermediate, or expert?": "Electrical experience level",
        "Do you know whether the wall is load-bearing?": "Whether the wall is load-bearing",
        "Could there be wiring, plumbing, or gas lines inside the wall?": "Whether hidden utilities may be present",
        "Is the leak near electrical outlets, switches, or appliances?": "Whether water is near live electrical equipment",
        "Is this a minor visible joint leak, or a hidden or main line leak?": "Whether the leak is accessible or part of a hidden/main line",
        "Is there dampness, mold, or peeling paint on the surface?": "Whether the surface has moisture damage or coating failure",
        "What is your experience level with this kind of painting work?": "Painting experience level",
    }
    return question_map.get(question, question.rstrip("?"))


def _gemini_enabled() -> bool:
    return os.getenv("GEMINI_ENABLED", "false").strip().lower() == "true"


def _gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


def _debug_trace_enabled() -> bool:
    return os.getenv("DEBUG_TRACE_ENABLED", "false").strip().lower() == "true"


def _attach_debug_trace(
    response: FollowupPlanResponse,
    debug_trace: DebugTrace | None,
) -> FollowupPlanResponse:
    if debug_trace is None:
        return response
    return response.model_copy(update={"debug_trace": debug_trace})


def _build_plan_debug_trace(
    *,
    response: FollowupPlanResponse,
    gemini_enabled: bool,
    gemini_used: bool,
    gemini_model: str,
    gemini_used_for: list[str],
    fallback_used: bool,
    notes: list[str],
    gemini_error: str | None = None,
    parsed_llm_response: dict[str, Any] | None = None,
    llm_response_text: str | None = None,
    llm_prompt: str | None = None,
) -> DebugTrace | None:
    if not _debug_trace_enabled():
        return None

    return DebugTrace(
        gemini_enabled=gemini_enabled,
        gemini_used=gemini_used,
        gemini_model=gemini_model,
        gemini_used_for=gemini_used_for,
        fallback_used=fallback_used,
        detected_task_intent=response.task_intent,
        detected_task_category=response.task_category,
        llm_suggested_risk_level=response.suggested_risk_level if gemini_used else None,
        follow_up_questions=response.follow_up_questions,
        critical_missing_info=response.critical_missing_info,
        selected_interpretation=response.selected_interpretation,
        notes=notes,
        gemini_error=gemini_error,
        parsed_llm_response=parsed_llm_response,
        llm_response_text=llm_response_text,
        llm_prompt=llm_prompt,
    )


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


def _normalize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        cleaned = _clean_sentence(item)
        if cleaned:
            normalized.append(cleaned)
    return list(dict.fromkeys(normalized))


def _normalize_category(value: Any) -> str:
    normalized = _normalize(str(value))
    if "/" in normalized:
        for candidate in CATEGORY_PROFILES:
            if candidate != "general" and candidate in normalized:
                return candidate
        if "general" in normalized:
            return "general"
    if normalized in CATEGORY_PROFILES:
        return normalized
    return "general"


def _normalize_task_intent(value: Any) -> TaskIntent | None:
    normalized = _normalize(str(value))
    valid_intents: tuple[TaskIntent, ...] = (
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
    )
    if normalized in valid_intents:
        return normalized
    return None


def _normalize_risk_level(value: Any) -> RiskLevel | None:
    candidate = _clean_sentence(value)
    if candidate in RISK_LEVEL_TO_SCORE:
        return candidate
    return None


def _clean_sentence(value: Any) -> str:
    return " ".join(str(value).strip().split())


def _trim_debug_text(value: str, limit: int = 2500) -> str:
    cleaned = _clean_sentence(value)
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit].rstrip()}..."


def _contains_any(text: str, keywords: tuple[str, ...] | list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _normalize(value: str) -> str:
    return " ".join(value.lower().strip().split())
