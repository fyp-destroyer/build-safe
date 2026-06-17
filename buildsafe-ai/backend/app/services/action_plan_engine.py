from __future__ import annotations

from dataclasses import dataclass

from app.schemas import (
    ActionPlanDebugTrace,
    ActionPlanRequest,
    ActionPlanResponse,
    ActionPlanStep,
    PlanType,
)


PREPARATION_ONLY_INTENTS = {
    "ceiling_fan_installation",
    "electrical_wiring_repair",
    "plumbing_leak_repair",
    "wall_demolition",
    "hvac_repair",
}

HARD_BLOCK_INTENTS = {
    "ceiling_fan_installation",
    "electrical_wiring_repair",
    "wall_demolition",
    "hvac_repair",
}

HARD_BLOCK_PHRASES = {
    "electrical wiring": "Electrical wiring work must be handled as preparation-only.",
    "wiring repair": "Electrical wiring repair must be handled as preparation-only.",
    "rewire": "Rewiring must be handled as preparation-only.",
    "main electrical panel": "Main electrical panel work must not be presented as DIY steps.",
    "breaker panel": "Main or breaker panel work must not be presented as DIY steps.",
    "distribution board": "Distribution board work must not be presented as DIY steps.",
    "gas line": "Gas line work must not be presented as DIY steps.",
    "gas pipe": "Gas pipe work must not be presented as DIY steps.",
    "gas leak": "Gas leak work must not be presented as DIY steps.",
    "load-bearing": "Load-bearing wall changes require professional review.",
    "load bearing": "Load-bearing wall changes require professional review.",
    "structural": "Structural work requires professional review.",
    "roof repair": "Roof repair at height must not be presented as DIY steps.",
    "roofing": "Roofing work must not be presented as DIY steps.",
    "hidden utilities": "Hidden utilities require professional preparation rather than DIY steps.",
    "hidden wiring": "Hidden wiring requires professional preparation rather than DIY steps.",
    "hidden wires": "Hidden wiring requires professional preparation rather than DIY steps.",
    "water near electrical": "Water near electrical sources must not be presented as DIY steps.",
    "water near outlets": "Water near electrical sources must not be presented as DIY steps.",
    "emergency leak": "Emergency leakage requires professional preparation rather than DIY steps.",
}

DISCLAIMER = (
    "This MVP plan is a safety aid, not a substitute for local codes, permits, "
    "manufacturer instructions, or a qualified professional inspection."
)


@dataclass(frozen=True)
class TemplateStep:
    title: str
    description: str
    safety_note: str
    estimated_time: str


@dataclass(frozen=True)
class ActionPlanTemplate:
    title: str
    summary: str
    prerequisites: tuple[str, ...]
    tools: tuple[str, ...]
    materials: tuple[str, ...]
    ppe: tuple[str, ...]
    steps: tuple[TemplateStep, ...]
    stop_conditions: tuple[str, ...]
    when_to_call_professional: tuple[str, ...]
    professional_questions: tuple[str, ...]


SAFE_TEMPLATES: dict[str, ActionPlanTemplate] = {
    "hanging_wall_decor": ActionPlanTemplate(
        title="Safe Work Plan: Hanging Wall Decor",
        summary=(
            "A controlled plan for hanging light-to-moderate wall decor after confirming "
            "the item weight, wall type, and fixing method."
        ),
        prerequisites=(
            "Confirm the item weight and approximate dimensions.",
            "Confirm the wall material before choosing hooks, anchors, or adhesive strips.",
            "Keep the work area clear and use stable footing for any overhead reach.",
        ),
        tools=(
            "measuring tape",
            "level",
            "pencil",
            "stud finder if drilling",
            "drill only if anchors are required",
        ),
        materials=(
            "picture hooks or wall anchors rated for the item weight",
            "wall plugs or screws matched to the wall type",
            "adhesive hooks only for light frames approved by the manufacturer",
        ),
        ppe=(
            "safety glasses if drilling",
            "work gloves",
        ),
        steps=(
            TemplateStep(
                "Confirm load and wall type",
                "Check the frame weight, hanging hardware, and wall material before selecting any fixing.",
                "Do not guess the wall type if the item is heavy or the fixing will be drilled.",
                "5-10 min",
            ),
            TemplateStep(
                "Choose a rated fixing",
                "Select a hook, anchor, or adhesive product rated above the item weight and compatible with the wall.",
                "Avoid adhesive strips for heavy, fragile, or valuable items.",
                "5 min",
            ),
            TemplateStep(
                "Mark the position",
                "Measure the desired location, mark the fixing point lightly, and check alignment with a level.",
                "Keep the placement reachable without leaning from a chair or unstable ladder.",
                "5-10 min",
            ),
            TemplateStep(
                "Install the fixing",
                "Install the selected fixing according to the product instructions and wall type.",
                "Stop before drilling if hidden wires or pipes may be behind the wall.",
                "5-15 min",
            ),
            TemplateStep(
                "Hang and verify stability",
                "Hang the item, then gently verify that it sits level and the fixing is not moving.",
                "Remove the item immediately if the fixing shifts, cracks, or pulls loose.",
                "5 min",
            ),
        ),
        stop_conditions=(
            "The wall cracks, crumbles, sounds hollow in an unexpected way, or the anchor pulls loose.",
            "The item is very heavy, fragile, or valuable and the wall/fixing strength is uncertain.",
            "The wall material is unknown or may contain hidden wiring, plumbing, or gas services.",
            "The placement requires unsafe ladder use, overreaching, or standing on furniture.",
        ),
        when_to_call_professional=(
            "Call a handyman or installer for heavy mirrors, tiled walls, masonry uncertainty, or high placements.",
            "Call a professional before drilling if hidden utilities may run behind the marked area.",
        ),
        professional_questions=(
            "What fixing type and load rating do you recommend for this wall material?",
            "Can you confirm whether hidden utilities are likely behind this wall section?",
            "Is this item too heavy for the available wall surface?",
        ),
    ),
    "wall_painting": ActionPlanTemplate(
        title="Safe Work Plan: Room Painting",
        summary=(
            "A basic room-painting plan focused on preparation, ventilation, surface condition, "
            "and safe cleanup."
        ),
        prerequisites=(
            "Confirm the surface is dry, stable, and free of active mold or severe peeling.",
            "Confirm the room can be ventilated during painting and drying.",
            "Move or cover furniture and protect floors before opening paint.",
        ),
        tools=(
            "paint roller",
            "brush set",
            "paint tray",
            "drop cloth",
            "painter's tape",
            "sanding block",
        ),
        materials=(
            "interior wall paint",
            "primer if the surface is stained, patched, or changing color sharply",
            "surface protection sheets",
            "mild cleaner",
        ),
        ppe=(
            "gloves",
            "mask for sanding or poor ventilation",
            "safety glasses for overhead work",
        ),
        steps=(
            TemplateStep(
                "Prepare the room",
                "Move furniture away, cover floors, remove loose items, and tape trim or edges.",
                "Keep exits clear and avoid creating trip hazards with sheets or cords.",
                "20-40 min",
            ),
            TemplateStep(
                "Clean and smooth the surface",
                "Wipe dust and grime, lightly sand rough areas, and remove loose flaking paint.",
                "Use a mask while sanding and pause if mold, dampness, or dust is significant.",
                "20-45 min",
            ),
            TemplateStep(
                "Prime if needed",
                "Apply primer to patched, stained, bare, or high-contrast surfaces and allow it to dry.",
                "Follow the product label for ventilation and drying time.",
                "30-60 min plus drying",
            ),
            TemplateStep(
                "Apply paint in controlled coats",
                "Cut in edges with a brush, roll broad areas evenly, and apply a second coat only after the first is dry.",
                "Keep windows or ventilation open according to the paint label.",
                "1-3 hr plus drying",
            ),
            TemplateStep(
                "Clean up and ventilate",
                "Remove tape before paint fully hardens, clean tools, and keep the room ventilated while drying.",
                "Keep children and pets away until surfaces are dry and fumes have cleared.",
                "20-30 min",
            ),
        ),
        stop_conditions=(
            "You find dampness, mold, bubbling plaster, or widespread peeling paint.",
            "The room cannot be ventilated or paint fumes cause dizziness, headache, or irritation.",
            "The job requires unsafe ladder work over stairs or high ceiling areas.",
            "Old paint may contain lead or another hazardous coating.",
        ),
        when_to_call_professional=(
            "Call a painter or remediation specialist for mold, dampness, failing plaster, or possible lead paint.",
            "Call a professional for high stairwells, exterior height work, or severe surface damage.",
        ),
        professional_questions=(
            "Does this surface need repair, sealing, or mold treatment before painting?",
            "Which primer and paint system is appropriate for this room?",
            "Is there any concern about older hazardous coatings?",
        ),
    ),
    "light_bulb_replacement": ActionPlanTemplate(
        title="Safe Work Plan: Light Bulb Replacement",
        summary=(
            "A simple like-for-like bulb replacement plan that avoids wiring or light-fitting work."
        ),
        prerequisites=(
            "Confirm this is only a standard bulb replacement, not wiring or fitting repair.",
            "Confirm the replacement bulb type and wattage are compatible with the fixture.",
            "Use stable access if the fixture is above normal reach.",
        ),
        tools=(
            "clean cloth",
            "stable step stool or ladder if needed",
        ),
        materials=(
            "compatible replacement bulb",
        ),
        ppe=(
            "safety glasses for overhead fixtures",
            "gloves or cloth for hot or fragile bulbs",
        ),
        steps=(
            TemplateStep(
                "Switch off and let the bulb cool",
                "Turn the light switch off and wait for the existing bulb to cool before touching it.",
                "Do not touch wiring, terminals, or damaged fittings.",
                "5-10 min",
            ),
            TemplateStep(
                "Set stable access",
                "Place a stable step stool or ladder on a level surface if the bulb is out of reach.",
                "Do not stand on chairs, beds, or furniture.",
                "2-5 min",
            ),
            TemplateStep(
                "Remove the old bulb",
                "Use a clean cloth or gloves to remove the old bulb carefully and place it somewhere safe.",
                "Stop if glass cracks, the fitting moves, or wiring is exposed.",
                "2-5 min",
            ),
            TemplateStep(
                "Install the compatible bulb",
                "Fit the replacement bulb gently without forcing it, then restore the switch to test it.",
                "Use only the fixture-approved bulb type and wattage.",
                "2-5 min",
            ),
        ),
        stop_conditions=(
            "The fixture is cracked, loose, scorched, buzzing, wet, or has exposed wiring.",
            "The bulb is broken in the socket.",
            "The fixture is too high to reach with stable access.",
            "The task involves wiring, the light fitting, a switch, or a breaker.",
        ),
        when_to_call_professional=(
            "Call an electrician if the fixture is damaged, wiring is exposed, or the bulb base is stuck.",
            "Call a professional if safe access at height cannot be set up.",
        ),
        professional_questions=(
            "Is this fixture safe to keep using?",
            "What bulb type and wattage should this fixture use?",
            "Does the loose, scorched, or flickering fixture need repair or replacement?",
        ),
    ),
    "furniture_assembly": ActionPlanTemplate(
        title="Safe Work Plan: Furniture Assembly",
        summary=(
            "A controlled assembly plan for flat-pack or kit furniture using the manufacturer's instructions."
        ),
        prerequisites=(
            "Read the manufacturer instructions before starting.",
            "Confirm all parts, fasteners, and anti-tip hardware are present.",
            "Clear enough floor space to assemble parts without forcing them.",
        ),
        tools=(
            "screwdriver set",
            "hex keys",
            "rubber mallet if specified by the manufacturer",
        ),
        materials=(
            "manufacturer-supplied fasteners",
            "anti-tip strap or wall anchor for tall furniture",
        ),
        ppe=(
            "work gloves",
            "closed-toe shoes",
        ),
        steps=(
            TemplateStep(
                "Inventory parts",
                "Lay out parts and fasteners, then match them against the instruction sheet.",
                "Do not substitute fasteners unless the manufacturer allows it.",
                "10-20 min",
            ),
            TemplateStep(
                "Prepare the assembly area",
                "Use a flat surface, protect finished faces, and keep small parts grouped.",
                "Keep children and pets away from small fasteners and unstable panels.",
                "5-10 min",
            ),
            TemplateStep(
                "Assemble in the listed order",
                "Follow the manufacturer sequence and hand-tighten fasteners until alignment is confirmed.",
                "Do not force misaligned parts; back up and check orientation.",
                "30-90 min",
            ),
            TemplateStep(
                "Tighten and stabilize",
                "Once aligned, tighten fasteners evenly and install any braces or back panels.",
                "Over-tightening can split panels or strip fasteners.",
                "10-20 min",
            ),
            TemplateStep(
                "Anchor tall furniture",
                "Install anti-tip hardware for wardrobes, bookcases, and other tall or top-heavy items.",
                "Do not use tall furniture until it is stable and anchored where required.",
                "10-20 min",
            ),
        ),
        stop_conditions=(
            "Parts are cracked, missing, warped, or do not align without force.",
            "Fasteners strip, panels split, or the item rocks after assembly.",
            "The furniture is tall or top-heavy and cannot be anchored safely.",
            "The assembly requires lifting pieces too heavy to handle alone.",
        ),
        when_to_call_professional=(
            "Call an assembler or handyman if large parts need two-person handling or wall anchoring is uncertain.",
            "Contact the supplier if structural parts or fasteners are missing or damaged.",
        ),
        professional_questions=(
            "Which wall anchor is appropriate for this furniture and wall type?",
            "Are any damaged or missing parts unsafe to substitute?",
            "Does this item need two-person handling or professional assembly?",
        ),
    ),
    "shelf_installation": ActionPlanTemplate(
        title="Supervised Work Plan: Shelf Installation",
        summary=(
            "A controlled plan for installing a small shelf after confirming the wall type, load, "
            "and hidden-utility risk."
        ),
        prerequisites=(
            "Confirm the shelf load, wall material, and fixing type before drilling.",
            "Check for likely hidden wiring or plumbing near the fixing points.",
            "Use a competent helper or supervisor if drilling, lifting, or wall type is uncertain.",
        ),
        tools=(
            "measuring tape",
            "level",
            "stud finder",
            "drill",
            "screwdriver",
        ),
        materials=(
            "shelf brackets",
            "anchors or screws rated for the wall type and expected load",
            "wall plugs if required",
        ),
        ppe=(
            "safety glasses",
            "work gloves",
            "dust mask if drilling masonry",
        ),
        steps=(
            TemplateStep(
                "Confirm load and wall type",
                "Check the expected load and choose fixings matched to the wall material.",
                "Do not install a loaded shelf into unknown or damaged wall material.",
                "10-15 min",
            ),
            TemplateStep(
                "Check fixing positions",
                "Mark bracket positions, check level, and use safe detection methods before drilling.",
                "Stop if there is any chance of hidden utilities behind the marks.",
                "10-15 min",
            ),
            TemplateStep(
                "Install brackets carefully",
                "Drill and fit anchors only where the wall type and hidden-utility risk have been checked.",
                "Wear eye protection and keep hands clear of the drill path.",
                "15-30 min",
            ),
            TemplateStep(
                "Mount and test the shelf",
                "Attach the shelf, tighten fixings evenly, and test with a light load before normal use.",
                "Do not fully load the shelf until all fixings remain firm under a gentle test.",
                "10-15 min",
            ),
        ),
        stop_conditions=(
            "You are unsure about wall material, studs, or hidden utilities.",
            "The wall crumbles, cracks, or anchors spin without gripping.",
            "The shelf will carry heavy, fragile, or overhead loads.",
            "The shelf is above shoulder height or requires unsafe ladder positioning.",
        ),
        when_to_call_professional=(
            "Call a handyman if the shelf is heavy, high, or mounted into masonry, tile, or unknown walls.",
            "Call a professional before drilling if hidden utilities may be present.",
        ),
        professional_questions=(
            "Which anchor type and load rating are appropriate for this wall?",
            "Can you confirm whether utilities run behind these fixing points?",
            "Is this shelf size or load suitable for this wall section?",
        ),
    ),
}


def generate_action_plan(payload: ActionPlanRequest) -> ActionPlanResponse:
    plan_type, allowed_by_risk = _plan_type_for_risk(payload.risk_level)
    template = SAFE_TEMPLATES.get(payload.task_intent)
    hard_block_reason = _hard_block_reason(payload)
    prep_only_reason = _preparation_only_reason(payload)
    unsupported_reason = ""

    allowed_to_show_steps = allowed_by_risk and template is not None
    reason_if_steps_blocked = ""

    if hard_block_reason:
        allowed_to_show_steps = False
        reason_if_steps_blocked = hard_block_reason
    elif prep_only_reason:
        allowed_to_show_steps = False
        reason_if_steps_blocked = prep_only_reason
    elif template is None:
        allowed_to_show_steps = False
        unsupported_reason = (
            "This task intent does not have a controlled safe-work template in the MVP, "
            "so the system returns a preparation checklist instead."
        )
        reason_if_steps_blocked = unsupported_reason
    elif not allowed_by_risk:
        reason_if_steps_blocked = _risk_block_reason(payload.risk_level)

    if allowed_to_show_steps and template is not None:
        return _build_safe_or_supervised_plan(
            payload=payload,
            template=template,
            plan_type=plan_type,
            reason_if_steps_blocked=reason_if_steps_blocked,
        )

    blocked_plan_type = _blocked_plan_type(payload.risk_level, plan_type)
    blocked_reason = reason_if_steps_blocked or _risk_block_reason(payload.risk_level)
    return _build_preparation_plan(
        payload=payload,
        plan_type=blocked_plan_type,
        reason_if_steps_blocked=blocked_reason,
    )


def _build_safe_or_supervised_plan(
    *,
    payload: ActionPlanRequest,
    template: ActionPlanTemplate,
    plan_type: PlanType,
    reason_if_steps_blocked: str,
) -> ActionPlanResponse:
    is_supervised = plan_type == "supervised_plan"
    title = template.title
    if is_supervised and not title.lower().startswith("supervised"):
        title = title.replace("Safe Work Plan", "Supervised Work Plan", 1)

    safety_notice = (
        "Proceed only with supervision, keep the work high-level, and stop if any listed hazard appears."
        if is_supervised
        else "Proceed only if the assessment details remain true and all listed safety checks are satisfied."
    )
    if payload.safety_warnings:
        safety_notice = f"{safety_notice} Key warning: {payload.safety_warnings[0]}"

    prerequisites = list(template.prerequisites)
    if is_supervised:
        prerequisites.insert(0, "Have a competent adult or experienced helper present before work starts.")

    return ActionPlanResponse(
        plan_type=plan_type,
        allowed_to_show_steps=True,
        title=title,
        summary=template.summary,
        safety_notice=safety_notice,
        prerequisites=_unique(prerequisites),
        tools_required=_unique([*template.tools, *payload.required_tools]),
        materials_required=_unique([*template.materials, *payload.required_materials]),
        ppe_required=_unique([*template.ppe, *payload.required_ppe]),
        steps=_numbered_steps(template.steps),
        stop_conditions=_unique([*template.stop_conditions, *payload.safety_warnings]),
        when_to_call_professional=_unique(template.when_to_call_professional),
        professional_questions=_unique(template.professional_questions),
        disclaimer=DISCLAIMER,
        debug_trace=ActionPlanDebugTrace(
            plan_type=plan_type,
            llm_used_for_plan=False,
            safety_restriction_applied=False,
            reason_if_steps_blocked=reason_if_steps_blocked,
        ),
    )


def _build_preparation_plan(
    *,
    payload: ActionPlanRequest,
    plan_type: PlanType,
    reason_if_steps_blocked: str,
) -> ActionPlanResponse:
    template = _preparation_template(payload)
    professional = _professional_label(payload)
    is_professional_only = plan_type == "professional_only_checklist"
    safety_notice = (
        "Do not attempt this task without a qualified professional."
        if is_professional_only
        else "Do not perform the risky parts yourself; use this checklist to prepare for a qualified professional."
    )
    if reason_if_steps_blocked:
        safety_notice = f"{safety_notice} {reason_if_steps_blocked}"

    return ActionPlanResponse(
        plan_type=plan_type,
        allowed_to_show_steps=False,
        title=template.title,
        summary=template.summary,
        safety_notice=safety_notice,
        prerequisites=_unique(template.prerequisites),
        tools_required=_unique(template.tools),
        materials_required=_unique(template.materials),
        ppe_required=_unique(template.ppe),
        steps=_numbered_steps(template.steps),
        stop_conditions=_unique([*template.stop_conditions, *payload.safety_warnings]),
        when_to_call_professional=_unique(
            [
                *template.when_to_call_professional,
                f"Contact {professional} before starting work on the risky part of this task.",
            ]
        ),
        professional_questions=_unique(template.professional_questions),
        disclaimer=DISCLAIMER,
        debug_trace=ActionPlanDebugTrace(
            plan_type=plan_type,
            llm_used_for_plan=False,
            safety_restriction_applied=True,
            reason_if_steps_blocked=reason_if_steps_blocked,
        ),
    )


def _preparation_template(payload: ActionPlanRequest) -> ActionPlanTemplate:
    if payload.task_intent == "ceiling_fan_installation":
        return ActionPlanTemplate(
            title="Preparation Checklist: Ceiling Fan Installation",
            summary="A preparation-only checklist for discussing the fan, wiring, and support box with an electrician.",
            prerequisites=(
                "Do not remove the existing fixture or perform wiring work yourself.",
                "Keep the fan model number, manual, and included mounting hardware together.",
                "Collect photos and measurements only from a stable, safe position.",
            ),
            tools=("phone or camera", "measuring tape", "notepad"),
            materials=("fan manual", "fan model number", "photos of existing fixture and switch locations"),
            ppe=("closed-toe shoes", "safety glasses if inspecting from a safe ladder"),
            steps=(
                TemplateStep(
                    "Document the current fixture",
                    "Take clear photos of the existing fixture, ceiling location, switches, and fan product label.",
                    "Do not open wiring connections or remove covers to take photos.",
                    "10-15 min",
                ),
                TemplateStep(
                    "Record ceiling and room details",
                    "Note ceiling height, room size, sloped ceiling conditions, and whether the area has damp exposure.",
                    "Measure only where you can stand safely.",
                    "10 min",
                ),
                TemplateStep(
                    "Check support information",
                    "Look for documentation or visible labeling that confirms whether the ceiling box is fan-rated.",
                    "Do not assume a light fixture box can hold a fan.",
                    "5-10 min",
                ),
                TemplateStep(
                    "Prepare electrician questions",
                    "List questions about wiring, fan-rated support, switch controls, and permits before booking the work.",
                    "Keep the task preparation-only until an electrician confirms the setup.",
                    "10 min",
                ),
            ),
            stop_conditions=(
                "Existing wiring, support, or fan-rated box status is unknown.",
                "The fixture is loose, buzzing, scorched, wet, or unusually warm.",
                "Access requires an unstable ladder or working above a stairwell.",
            ),
            when_to_call_professional=("Book an electrician before any wiring, mounting, or fixture removal.",),
            professional_questions=(
                "Is the ceiling box fan-rated and properly supported?",
                "Is the existing wiring suitable for this fan and switch setup?",
                "Are permits, isolation steps, or code requirements needed for this installation?",
            ),
        )

    if payload.task_intent == "electrical_wiring_repair":
        return ActionPlanTemplate(
            title="Professional Checklist: Electrical Wiring Repair",
            summary="A professional-only checklist for documenting the issue while avoiding contact with wiring.",
            prerequisites=(
                "Do not touch exposed wires, terminals, switches, outlets, or damaged electrical parts.",
                "Keep people away from the affected area.",
                "Use normal switches or breakers only if you can do so safely and without contacting damaged parts.",
            ),
            tools=("phone or camera", "notepad", "flashlight used from a safe distance"),
            materials=("photos of affected area", "room or circuit location notes", "appliance or fixture model details"),
            ppe=("closed-toe shoes", "dry hands and dry footing"),
            steps=(
                TemplateStep(
                    "Keep distance",
                    "Create a clear boundary around the affected area and keep others away.",
                    "Do not touch wiring or wet electrical surfaces.",
                    "Immediate",
                ),
                TemplateStep(
                    "Record visible facts",
                    "From a safe distance, note where the issue is, what changed, and whether there is heat, smell, sparking, or water nearby.",
                    "Do not remove covers or open devices.",
                    "5-10 min",
                ),
                TemplateStep(
                    "Collect reference photos",
                    "Take photos only if you can do so without touching the electrical equipment.",
                    "Stop if there is smoke, sparking, heat, or water near electricity.",
                    "5 min",
                ),
                TemplateStep(
                    "Contact an electrician",
                    "Share the notes and photos with a qualified electrician or emergency service if conditions are urgent.",
                    "Treat active sparking, smoke, or burning smell as urgent.",
                    "10 min",
                ),
            ),
            stop_conditions=(
                "Sparking, smoke, burning smell, heat, buzzing, or exposed conductors are present.",
                "Water or dampness is near electrical parts.",
                "The issue involves a breaker panel, service cable, or unknown circuit.",
            ),
            when_to_call_professional=("Call an electrician before any inspection, repair, or reset attempt.",),
            professional_questions=(
                "What isolation or emergency steps are needed before inspection?",
                "Could this circuit or device be unsafe to energize?",
                "Is repair, replacement, or code remediation required?",
            ),
        )

    if payload.task_intent == "plumbing_leak_repair":
        return ActionPlanTemplate(
            title="Preparation Checklist: Plumbing Leak",
            summary="A preparation-only checklist for limiting damage and giving a plumber the right information.",
            prerequisites=(
                "Do not open walls, floors, or concealed pipe areas yourself.",
                "Keep water away from outlets, switches, appliances, and extension cords.",
                "If there is an accessible shutoff valve and it is safe to use, note whether it controls the leak.",
            ),
            tools=("phone or camera", "bucket or tray for active drips", "towels", "notepad"),
            materials=("photos of leak location", "notes on pipe material if visible", "water bill or shutoff location notes"),
            ppe=("waterproof gloves", "closed-toe shoes"),
            steps=(
                TemplateStep(
                    "Protect the area",
                    "Move belongings away and place a bucket or towels to limit spread while waiting for help.",
                    "Avoid standing water and keep the area clear of electrical items.",
                    "5-10 min",
                ),
                TemplateStep(
                    "Document leak details",
                    "Note where the leak appears, when it started, flow rate, and whether it worsens when fixtures run.",
                    "Do not cut, open, or dismantle hidden pipe areas.",
                    "10 min",
                ),
                TemplateStep(
                    "Check safe shutoff options",
                    "Identify nearby fixture valves or the main shutoff location if visible and accessible.",
                    "Do not force stuck valves or touch electrical equipment near water.",
                    "5-10 min",
                ),
                TemplateStep(
                    "Prepare plumber questions",
                    "Share photos, leak timing, shutoff notes, and any nearby electrical risks with a plumber.",
                    "Treat water near electricity as urgent professional work.",
                    "10 min",
                ),
            ),
            stop_conditions=(
                "Water is near outlets, switches, appliances, or electrical panels.",
                "The leak is hidden in a wall, floor, ceiling, or main line.",
                "Water flow is increasing or causing ceiling sagging, wall swelling, or slipping hazards.",
            ),
            when_to_call_professional=("Call a plumber for hidden, main-line, recurring, or electrically risky leaks.",),
            professional_questions=(
                "Where is the likely leak source and does it require opening a wall or floor?",
                "Which shutoff should be used before repair?",
                "Is there water damage, mold risk, or electrical coordination needed?",
            ),
        )

    if payload.task_intent == "wall_demolition":
        return ActionPlanTemplate(
            title="Professional Checklist: Wall Demolition",
            summary="A professional-only checklist for wall removal, structural review, and hidden-utility checks.",
            prerequisites=(
                "Do not demolish, cut, drill deeply, or remove finishes until the wall is assessed.",
                "Collect drawings, prior renovation notes, or building approvals if available.",
                "Keep the area clear and avoid disturbing suspected utility routes.",
            ),
            tools=("phone or camera", "measuring tape", "notepad"),
            materials=("photos of both sides of the wall", "room measurements", "building drawings if available"),
            ppe=("closed-toe shoes", "dust mask if the area is already dusty"),
            steps=(
                TemplateStep(
                    "Document the wall",
                    "Take photos of both sides, nearby rooms, ceiling/floor connections, outlets, switches, vents, and plumbing fixtures.",
                    "Do not open the wall or remove material to investigate.",
                    "15-20 min",
                ),
                TemplateStep(
                    "Collect measurements",
                    "Measure wall length, height, thickness if visible, and distances to nearby openings or structural elements.",
                    "Measure from safe standing positions only.",
                    "10-15 min",
                ),
                TemplateStep(
                    "Gather building information",
                    "Find drawings, renovation history, or permit documents that may show structure and services.",
                    "Treat missing information as a reason to pause, not as permission to start.",
                    "15-30 min",
                ),
                TemplateStep(
                    "Book professional review",
                    "Contact a structural engineer, mason, or contractor to confirm load-bearing status and hidden utilities.",
                    "Do not begin demolition before written or clear professional guidance.",
                    "10-20 min",
                ),
            ),
            stop_conditions=(
                "Load-bearing status is unknown or the wall may support beams, joists, or upper floors.",
                "Wiring, plumbing, gas lines, ducts, or shared apartment services may be inside.",
                "Permits, structural drawings, or professional confirmation are missing.",
            ),
            when_to_call_professional=("Call a structural engineer, mason, or contractor before any demolition work.",),
            professional_questions=(
                "Is this wall load-bearing or connected to structural elements?",
                "What utilities could be hidden inside this wall?",
                "Are permits, temporary supports, or inspections required?",
            ),
        )

    if payload.task_intent == "hvac_repair":
        return ActionPlanTemplate(
            title="Preparation Checklist: HVAC Repair",
            summary="A preparation-only checklist for documenting HVAC symptoms without opening sealed or electrical components.",
            prerequisites=(
                "Do not open sealed refrigerant systems, gas appliances, or hardwired electrical compartments.",
                "Use normal thermostat or power controls only if they are safe and accessible.",
                "Keep vents and equipment access clear for the technician.",
            ),
            tools=("phone or camera", "notepad", "thermostat reading"),
            materials=("equipment model and serial number", "filter size if visible", "photos of error codes or labels"),
            ppe=("closed-toe shoes", "work gloves for clearing nearby clutter only"),
            steps=(
                TemplateStep(
                    "Record symptoms",
                    "Note noises, smells, error codes, temperature behavior, and when the issue started.",
                    "Stop immediately if there is a burning smell, gas smell, smoke, or electrical arcing.",
                    "10 min",
                ),
                TemplateStep(
                    "Collect equipment details",
                    "Photograph model labels, thermostat settings, and visible error messages.",
                    "Do not remove service panels to find labels.",
                    "10 min",
                ),
                TemplateStep(
                    "Clear safe access",
                    "Move storage or clutter away from the equipment so a technician can inspect it.",
                    "Do not disturb wiring, gas lines, refrigerant lines, or condensate pumps.",
                    "10-15 min",
                ),
                TemplateStep(
                    "Prepare technician questions",
                    "Ask about electrical, refrigerant, gas, warranty, and maintenance implications before repair.",
                    "Keep the task preparation-only until a qualified technician inspects it.",
                    "10 min",
                ),
            ),
            stop_conditions=(
                "Gas smell, burning smell, smoke, sparking, or tripping breakers are present.",
                "The issue involves refrigerant lines, sealed equipment, or combustion appliances.",
                "Water leakage is near electrical controls or outlets.",
            ),
            when_to_call_professional=("Call an HVAC technician before opening equipment or replacing internal parts.",),
            professional_questions=(
                "Is this an electrical, refrigerant, airflow, drainage, or control fault?",
                "Is the unit safe to keep running before repair?",
                "Does the repair affect warranty, gas safety, or code compliance?",
            ),
        )

    if payload.task_intent == "tile_installation":
        return ActionPlanTemplate(
            title="Preparation Checklist: Tile Installation",
            summary="A preparation checklist for tile work where wet-area, substrate, or cutting risk needs review.",
            prerequisites=(
                "Confirm whether the area is wet, cracked, uneven, or tied into waterproofing.",
                "Do not start demolition or waterproofing work if substrate condition is uncertain.",
                "Collect tile, grout, adhesive, and area details before seeking advice.",
            ),
            tools=("phone or camera", "measuring tape", "notepad"),
            materials=("area measurements", "photos of substrate", "tile and grout product details"),
            ppe=("closed-toe shoes", "dust mask if the area is already dusty"),
            steps=(
                TemplateStep(
                    "Document the area",
                    "Take photos of the surface, edges, fixtures, drains, and any cracks or damp patches.",
                    "Do not remove existing tiles or waterproofing layers just to inspect.",
                    "10-15 min",
                ),
                TemplateStep(
                    "Measure and note conditions",
                    "Record area dimensions, tile size, wet-area exposure, and whether cuts around fixtures are needed.",
                    "Avoid cutting or drilling until the surface and utility risks are clear.",
                    "10-15 min",
                ),
                TemplateStep(
                    "Prepare installer questions",
                    "Ask about waterproofing, substrate repair, movement joints, dust control, and tile cutting.",
                    "Treat bathrooms, showers, and wet areas as higher risk.",
                    "10 min",
                ),
            ),
            stop_conditions=(
                "The area is a shower, bathroom wet zone, balcony, or another waterproofed surface.",
                "The substrate is cracked, damp, uneven, loose, or moldy.",
                "Tile cutting, dust control, or hidden utilities are uncertain.",
            ),
            when_to_call_professional=("Call a tiler for wet areas, waterproofing, failed substrate, or complex cuts.",),
            professional_questions=(
                "Does this area require waterproofing or substrate repair before tiling?",
                "What adhesive, grout, and movement joints are suitable here?",
                "How will dust, cutting, and hidden utility risks be controlled?",
            ),
        )

    return ActionPlanTemplate(
        title="Preparation Checklist: Task Review",
        summary="A conservative preparation checklist because this task is outside the MVP's controlled DIY templates.",
        prerequisites=(
            "Do not start risky work until the missing safety details are clear.",
            "Collect task photos, measurements, and site conditions before proceeding.",
            "Use the assessment risk level as the authority for deciding whether professional help is needed.",
        ),
        tools=("phone or camera", "measuring tape", "notepad"),
        materials=("task photos", "measurements", "product manuals or labels if relevant"),
        ppe=("closed-toe shoes", "work gloves if handling loose items only"),
        steps=(
            TemplateStep(
                "Collect task information",
                "Take photos, note measurements, and list what is unknown about the work area.",
                "Do not expose hidden utilities or dismantle risky parts to gather information.",
                "10-20 min",
            ),
            TemplateStep(
                "Review safety blockers",
                "Check the assessment warnings, required PPE, and any professional recommendation.",
                "Treat uncertainty about utilities, structure, height, gas, or electricity as a reason to pause.",
                "5-10 min",
            ),
            TemplateStep(
                "Prepare professional questions",
                "Write down what you need confirmed before any work begins.",
                "Do not convert this checklist into execution steps for unsupported tasks.",
                "10 min",
            ),
        ),
        stop_conditions=(
            "The task involves gas, electrical wiring, structure, roof height, hidden utilities, or emergency leakage.",
            "The required safety checks cannot be confirmed.",
            "The work area changes or new hazards appear.",
        ),
        when_to_call_professional=("Call a qualified professional whenever the assessment recommends or requires one.",),
        professional_questions=(
            "What hazards need to be isolated before work begins?",
            "Are permits, inspections, or specialist trades required?",
            "What information should I provide before the site visit?",
        ),
    )


def _plan_type_for_risk(risk_level: str) -> tuple[PlanType, bool]:
    if risk_level == "Safe DIY":
        return "safe_diy_plan", True
    if risk_level == "DIY with supervision":
        return "supervised_plan", True
    if risk_level == "Professional recommended":
        return "preparation_checklist", False
    return "professional_only_checklist", False


def _blocked_plan_type(risk_level: str, original_plan_type: PlanType) -> PlanType:
    if risk_level in {"Professional required", "Dangerous / permit-required / do not attempt"}:
        return "professional_only_checklist"
    if original_plan_type == "professional_only_checklist":
        return original_plan_type
    return "preparation_checklist"


def _risk_block_reason(risk_level: str) -> str:
    if risk_level == "Professional recommended":
        return "Risk level is Professional recommended, so the system only returns a preparation checklist."
    if risk_level == "Professional required":
        return "Risk level is Professional required, so DIY execution steps are blocked."
    if risk_level == "Dangerous / permit-required / do not attempt":
        return "Risk level is Dangerous / permit-required / do not attempt, so DIY execution steps are blocked."
    return ""


def _hard_block_reason(payload: ActionPlanRequest) -> str:
    if payload.task_intent in HARD_BLOCK_INTENTS:
        return _reason_for_hard_block_intent(payload.task_intent)

    haystack = _combined_payload_text(payload)
    for phrase, reason in HARD_BLOCK_PHRASES.items():
        if phrase in haystack:
            return reason
    return ""


def _reason_for_hard_block_intent(task_intent: str) -> str:
    reasons = {
        "ceiling_fan_installation": "Ceiling fan installation involves electrical wiring and overhead support checks.",
        "electrical_wiring_repair": "Electrical wiring repair must not be presented as DIY steps.",
        "wall_demolition": "Wall demolition may involve structure and hidden utilities.",
        "hvac_repair": "HVAC repair may involve sealed systems, gas, or electrical components.",
    }
    return reasons.get(task_intent, "This task is blocked from detailed DIY steps by safety policy.")


def _preparation_only_reason(payload: ActionPlanRequest) -> str:
    if payload.task_intent in PREPARATION_ONLY_INTENTS:
        return f"{_format_intent(payload.task_intent)} is handled as preparation-only in this MVP."
    if payload.task_intent == "tile_installation" and _tile_is_complex_or_wet(payload):
        return "Complex or wet-area tile installation is handled as preparation-only."
    return ""


def _tile_is_complex_or_wet(payload: ActionPlanRequest) -> bool:
    haystack = _combined_payload_text(payload)
    return any(
        phrase in haystack
        for phrase in (
            "bathroom",
            "shower",
            "wet area",
            "wet-area",
            "waterproof",
            "waterproofing",
            "balcony",
            "drain",
            "mold",
            "damp",
            "cracked",
            "uneven",
            "complex",
        )
    )


def _combined_payload_text(payload: ActionPlanRequest) -> str:
    answer_text = " ".join(f"{key} {value}" for key, value in payload.followup_answers.items())
    return _normalize(
        " ".join(
            [
                payload.task_description,
                payload.task_intent,
                payload.task_category,
                payload.risk_level,
                " ".join(payload.safety_warnings),
                answer_text,
            ]
        )
    )


def _numbered_steps(steps: tuple[TemplateStep, ...]) -> list[ActionPlanStep]:
    return [
        ActionPlanStep(
            step_number=index,
            title=step.title,
            description=step.description,
            safety_note=step.safety_note,
            estimated_time=step.estimated_time,
        )
        for index, step in enumerate(steps, start=1)
    ]


def _professional_label(payload: ActionPlanRequest) -> str:
    professional = payload.recommended_professional_category.strip()
    if professional:
        return professional
    category_map = {
        "ceiling_fan_installation": "a qualified electrician",
        "electrical_wiring_repair": "a qualified electrician",
        "plumbing_leak_repair": "a licensed plumber",
        "wall_demolition": "a structural engineer, mason, or contractor",
        "hvac_repair": "a qualified HVAC technician",
        "tile_installation": "a qualified tiler",
    }
    return category_map.get(payload.task_intent, "a qualified professional")


def _format_intent(task_intent: str) -> str:
    return task_intent.replace("_", " ").title()


def _unique(values: tuple[str, ...] | list[str]) -> list[str]:
    cleaned = [" ".join(value.strip().split()) for value in values if value.strip()]
    return list(dict.fromkeys(cleaned))


def _normalize(value: str) -> str:
    return " ".join(value.lower().strip().split())
