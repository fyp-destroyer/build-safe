from __future__ import annotations

from dataclasses import dataclass

from app.schemas import TaskIntent


@dataclass(frozen=True)
class TaskIntentResult:
    task_intent: TaskIntent
    task_category: str
    is_ambiguous: bool
    possible_interpretations: list[str]
    selected_interpretation: str


INTENT_TO_CATEGORY: dict[TaskIntent, str] = {
    "hanging_wall_decor": "carpentry",
    "wall_painting": "painting",
    "electrical_fixture_installation": "electrical",
    "electrical_wiring_repair": "electrical",
    "plumbing_leak_repair": "plumbing",
    "wall_demolition": "masonry_demolition",
    "tile_installation": "tiling",
    "furniture_assembly": "carpentry",
    "shelf_installation": "carpentry",
    "light_bulb_replacement": "electrical",
    "ceiling_fan_installation": "electrical",
    "hvac_repair": "hvac",
    "general_diy": "general",
}


def detect_task_intent(task_description: str) -> TaskIntentResult:
    task_text = _normalize(task_description)

    hanging_decor = _is_hanging_wall_decor(task_text)
    wall_painting = _is_wall_painting(task_text)

    if hanging_decor:
        return TaskIntentResult(
            task_intent="hanging_wall_decor",
            task_category=INTENT_TO_CATEGORY["hanging_wall_decor"],
            is_ambiguous=wall_painting,
            possible_interpretations=_possible_interpretations(task_text, hanging_decor, wall_painting),
            selected_interpretation=(
                "The user wants to hang framed artwork or wall decor, not paint the room."
            ),
        )

    if wall_painting:
        return TaskIntentResult(
            task_intent="wall_painting",
            task_category=INTENT_TO_CATEGORY["wall_painting"],
            is_ambiguous=False,
            possible_interpretations=[],
            selected_interpretation=(
                "The user wants to apply paint to the room, wall, or surface."
            ),
        )

    ordered_checks: list[tuple[TaskIntent, tuple[str, ...], str]] = [
        (
            "light_bulb_replacement",
            ("replace light bulb", "replace a light bulb", "change light bulb", "change a light bulb", "swap bulb"),
            "The user wants to replace a bulb rather than repair broader wiring.",
        ),
        (
            "ceiling_fan_installation",
            ("ceiling fan",),
            "The user wants to install or replace a ceiling fan.",
        ),
        (
            "electrical_wiring_repair",
            ("wiring", "wire repair", "repair outlet", "fix outlet", "breaker", "switch wiring", "socket wiring"),
            "The user is dealing with wiring, outlets, switches, or similar electrical repair work.",
        ),
        (
            "electrical_fixture_installation",
            ("light fixture", "install fixture", "install light", "replace fixture", "install switch", "install outlet"),
            "The user wants to install or replace an electrical fixture or fitting.",
        ),
        (
            "plumbing_leak_repair",
            ("leaking pipe", "pipe leak", "fix leak", "sink leak", "tap leak", "faucet leak", "leak"),
            "The user wants to fix a leak or accessible plumbing fault.",
        ),
        (
            "wall_demolition",
            ("break a wall", "remove wall", "knock down wall", "tear down wall", "demolition", "partition wall"),
            "The user wants to remove, break, or demolish a wall or partition.",
        ),
        (
            "tile_installation",
            ("install tile", "install tiles", "tile wall", "tile floor", "tiling", "grout tiles"),
            "The user wants to install or replace tiles.",
        ),
        (
            "furniture_assembly",
            ("assemble furniture", "build furniture", "assemble bed", "assemble desk", "assemble wardrobe"),
            "The user wants to assemble furniture rather than modify the building fabric.",
        ),
        (
            "shelf_installation",
            ("install shelf", "mount shelf", "hang shelf", "put up shelf", "floating shelf"),
            "The user wants to mount a shelf.",
        ),
        (
            "hvac_repair",
            ("hvac", "air conditioner", "ac unit", "thermostat", "heat pump", "furnace", "duct"),
            "The user wants HVAC servicing or repair.",
        ),
    ]

    for task_intent, keywords, interpretation in ordered_checks:
        if _contains_any(task_text, keywords):
            return TaskIntentResult(
                task_intent=task_intent,
                task_category=INTENT_TO_CATEGORY[task_intent],
                is_ambiguous=False,
                possible_interpretations=[],
                selected_interpretation=interpretation,
            )

    return TaskIntentResult(
        task_intent="general_diy",
        task_category=INTENT_TO_CATEGORY["general_diy"],
        is_ambiguous=False,
        possible_interpretations=[],
        selected_interpretation="The task is being treated as a general DIY request.",
    )


def category_for_intent(task_intent: TaskIntent) -> str:
    return INTENT_TO_CATEGORY.get(task_intent, "general")


def _is_hanging_wall_decor(task_text: str) -> bool:
    verb_cues = ("hang", "hanging", "mount", "put up", "attach")
    object_cues = (
        "painting",
        "picture",
        "frame",
        "artwork",
        "mirror",
        "wall decor",
        "wall decoration",
        "canvas",
        "poster",
    )
    direct_phrases = (
        "hang a painting",
        "hang painting",
        "hanging a painting",
        "mount a painting",
        "put up a painting",
        "hang a picture",
        "mount a frame",
        "hang a mirror",
        "mount a mirror",
        "hang artwork",
        "wall decor",
    )
    return _contains_any(task_text, direct_phrases) or (
        _contains_any(task_text, verb_cues) and _contains_any(task_text, object_cues)
    )


def _is_wall_painting(task_text: str) -> bool:
    if _is_hanging_wall_decor(task_text):
        return False

    direct_phrases = (
        "paint my room",
        "paint my bedroom",
        "paint the bedroom",
        "paint the room",
        "paint the wall",
        "paint the walls",
        "repaint wall",
        "repaint the wall",
        "apply paint",
        "wall painting",
        "painting the wall",
        "painting my bedroom",
    )
    broad_phrases = ("paint room", "paint bedroom", "paint wall", "paint walls", "primer")
    return _contains_any(task_text, direct_phrases) or _contains_any(task_text, broad_phrases)


def _possible_interpretations(
    task_text: str,
    hanging_decor: bool,
    wall_painting: bool,
) -> list[str]:
    interpretations: list[str] = []
    if hanging_decor:
        interpretations.append("Hanging framed artwork or wall decor on a wall")
    if wall_painting:
        interpretations.append("Applying paint to the room or wall surfaces")
    if not interpretations and "painting" in task_text:
        interpretations.extend(
            [
                "Hanging framed artwork or wall decor on a wall",
                "Applying paint to the room or wall surfaces",
            ]
        )
    return interpretations


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _normalize(value: str) -> str:
    return " ".join(value.lower().strip().split())
