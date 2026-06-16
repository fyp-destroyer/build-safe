from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models import CATEGORY_PROFILES, MIN_SCORE_BY_LEVEL, RISK_LEVELS
from app.schemas import AssessmentRequest

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _load_safety_rules() -> list[dict[str, Any]]:
    with (DATA_DIR / "safety_rules.json").open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return payload["rules"]


def _normalize(value: str) -> str:
    return " ".join(value.lower().strip().split())


def _contains_any(text: str, keywords: list[str] | tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _score_to_level(score: int) -> str:
    if score >= 81:
        return RISK_LEVELS[5]
    if score >= 61:
        return RISK_LEVELS[4]
    if score >= 41:
        return RISK_LEVELS[3]
    if score >= 21:
        return RISK_LEVELS[2]
    return RISK_LEVELS[1]


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

    unknown_values = {"", "unknown", "not sure", "unsure", "n/a", "na", None}
    return any(str(value).strip().lower() in unknown_values for value in answers.values())


def assess_risk(request: AssessmentRequest) -> dict[str, Any]:
    task_text = _normalize(request.task_description)
    skill_level = _normalize(request.user_skill_level)
    urgency = _normalize(request.urgency)
    category = _detect_category(task_text)
    risk_score = CATEGORY_PROFILES[category].base_score
    rules_triggered: list[str] = []
    safety_warnings: list[str] = []

    # Future ML integration point:
    # A trained classifier can produce category/risk priors here, then the
    # rules below can remain as a safety guardrail for high-risk hazards.
    for rule in _load_safety_rules():
        if _contains_any(task_text, rule["keywords"]):
            category = rule.get("category", category)
            risk_score = max(risk_score, MIN_SCORE_BY_LEVEL[rule["min_risk_level"]])
            risk_score += int(rule.get("score_boost", 0))
            rules_triggered.append(f'{rule["id"]}: {rule["description"]}')
            warning = rule.get("warning")
            if warning:
                safety_warnings.append(warning)

    trade_categories = {
        "electrical",
        "plumbing",
        "masonry_demolition",
        "roofing",
        "gas",
        "structural",
    }
    if skill_level == "beginner" and category in trade_categories:
        risk_score += 10
        rules_triggered.append(
            "SKILL_BEGINNER_TRADE: Beginner skill level increases risk for trade work."
        )
    elif skill_level == "expert" and category not in {"gas", "structural", "roofing"}:
        risk_score -= 5
        rules_triggered.append(
            "SKILL_EXPERT_OFFSET: Expert skill slightly reduces risk for non-critical tasks."
        )

    emergency_keywords = (
        "electric",
        "wire",
        "water",
        "leak",
        "gas",
        "structure",
        "wall",
        "roof",
    )
    if urgency == "emergency" and (
        category in trade_categories or _contains_any(task_text, emergency_keywords)
    ):
        risk_score = max(risk_score + 15, MIN_SCORE_BY_LEVEL[4])
        rules_triggered.append(
            "URGENCY_EMERGENCY_HAZARD: Emergency timing increases risk for utility or structural work."
        )
        safety_warnings.append(
            "Emergency conditions can hide serious hazards. Stabilize the area and contact emergency services if life, fire, gas, or flooding risk is present."
        )

    critical_info_categories = {"electrical", "plumbing", "masonry_demolition", "gas", "structural", "roofing"}
    if category in critical_info_categories and _answers_missing_or_unknown(request.answers_to_followups):
        risk_score += 8
        rules_triggered.append(
            "MISSING_CRITICAL_INFO: Missing safety details increase uncertainty."
        )

    risk_score = min(max(risk_score, 0), 100)
    confidence_score = 0.86 if rules_triggered else 0.68
    if "MISSING_CRITICAL_INFO" in " ".join(rules_triggered):
        confidence_score -= 0.08

    risk_level = _score_to_level(risk_score)
    category_label = CATEGORY_PROFILES.get(category, CATEGORY_PROFILES["general"]).label
    explanation = _build_explanation(category_label, risk_level, rules_triggered)

    return {
        "task_category": category_label,
        "category_key": category,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "confidence_score": round(max(confidence_score, 0.5), 2),
        "explanation": explanation,
        "safety_warnings": _unique(safety_warnings),
        "rules_triggered": _unique(rules_triggered),
    }


def _build_explanation(category_label: str, risk_level: str, rules_triggered: list[str]) -> str:
    if not rules_triggered:
        return (
            f"This looks like a {category_label.lower()} task with no critical hazard keywords detected. "
            f"The current MVP classifies it as {risk_level.lower()} based on base category risk."
        )

    return (
        f"This task was classified as {category_label.lower()} and reached {risk_level.lower()} "
        "because one or more safety rules matched the task details and context."
    )


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
