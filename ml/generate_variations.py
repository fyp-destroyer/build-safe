"""Phase 2 step 2+3: template-based variation generation + weak labeling.

Reads ml/data/seed_examples.json (hand-written, authoritative), writes
ml/data/generated_examples.json. Seeds are never relabelled here.

Weak-labeling rules applied (see ml/data/README.md for the rationale):
  WL-1  label-preserving  - variant inherits the parent label verbatim
  WL-2  escalation-only   - stripping a stated safety confirmation makes the
                            condition unaddressed, which forces risk_level 5
No rule ever lowers a risk level.
"""

import json
import re
from pathlib import Path

SEEDS = Path("ml/data/seed_examples.json")
OUT = Path("ml/data/generated_examples.json")

seeds = json.loads(SEEDS.read_text(encoding="utf-8"))

# ---- assign stable ids to seeds (needed so variants can reference a parent)
for i, e in enumerate(seeds, 1):
    if "id" not in e:
        ordered = {"id": f"seed-{i:04d}"}
        ordered.update(e)
        seeds[i - 1] = ordered
SEEDS.write_text(json.dumps(seeds, indent=2) + "\n", encoding="utf-8")

by_text = {e["task_text"]: e for e in seeds}
LABELS = {1: "safe_diy", 2: "diy_with_supervision", 3: "professional_recommended",
          4: "professional_required", 5: "dangerous"}
Q = {
    "power_isolated": "Have you confirmed the power to this circuit is fully isolated at the breaker before starting?",
    "load_bearing_confirmed": "Have you confirmed the wall or structure involved is NOT load-bearing?",
    "gas_line_present": "Have you confirmed there is no gas line present near this work area?",
}

generated = []


def emit(parent, text, rule, **overrides):
    rec = {k: (list(v) if isinstance(v, list) else v) for k, v in parent.items()}
    rec.pop("id", None)
    rec["task_text"] = text
    rec.update(overrides)
    rec["risk_label"] = LABELS[rec["risk_level"]]
    out = {"id": None, "variant_of": parent["id"], "generation_rule": rule}
    out.update(rec)
    generated.append(out)


# ---------------------------------------------------------------- WL-2
# Escalation-only. Each stripped text is hand-written, not regex-derived,
# because removing a confirmation clause changes a safety label. Result is
# always the "condition never addressed" case -> follow-up returns, risk 5.
# (The ceiling-fan confirmation variant is deliberately excluded: stripping
# it reproduces an existing seed verbatim.)
STRIPS = [
    # (parent task_text prefix, stripped text, followup field, professional_category)
    ("replace a worn out wall outlet in the living room -", "replace a worn out wall outlet in the living room", "power_isolated", "electrician"),
    ("swap a light switch for a dimmer,", "swap a light switch for a dimmer", "power_isolated", "electrician"),
    ("replace a ceiling light fixture in the hallway -", "replace a ceiling light fixture in the hallway", "power_isolated", "electrician"),
    ("install a hardwired under-cabinet light off an existing junction box,", "install a hardwired under-cabinet light off an existing junction box", "power_isolated", "electrician"),
    ("replace a bathroom extractor fan wired into the lighting circuit,", "replace a bathroom extractor fan wired into the lighting circuit", "power_isolated", "electrician"),
    ("install an outdoor motion sensor floodlight above the garage door,", "install an outdoor motion sensor floodlight above the garage door", "power_isolated", "electrician"),
    ("replace a faulty GFCI outlet in the bathroom -", "replace a faulty GFCI outlet in the bathroom", "power_isolated", "electrician"),
    ("move a light switch to the other side of the doorway, cutting into the wall -", "move a light switch to the other side of the doorway, cutting into the wall", "power_isolated", "electrician"),
    ("replace the aluminium wiring in a 1970s house with copper,", "replace the aluminium wiring in a 1970s house with copper", "power_isolated", "electrician"),
    ("rewire the lighting circuit on the whole first floor,", "rewire the lighting circuit on the whole first floor", "power_isolated", "electrician"),
    ("cut and tile around the kitchen sockets -", "cut and tile around the kitchen sockets", "power_isolated", "electrician"),
    ("install a bathroom extractor fan ducted through the external wall -", "install a bathroom extractor fan ducted through the external wall", "power_isolated", "hvac_technician"),
    ("fit a wired room thermostat to replace the old one,", "fit a wired room thermostat to replace the old one", "power_isolated", "hvac_technician"),
    ("cut a new doorway through an internal stud partition -", "cut a new doorway through an internal stud partition", "load_bearing_confirmed", "structural_engineer"),
    ("cut a new window opening in a single skin garage wall -", "cut a new window opening in a single skin garage wall", "load_bearing_confirmed", "structural_engineer"),
    ("replace the lead water main from the street into the house -", "replace the lead water main from the street into the house", "gas_line_present", "plumber"),
    ("dig out and level a large area of the garden for a patio -", "dig out and level a large area of the garden for a patio", "gas_line_present", "general_contractor"),
]

for prefix, stripped, field, prof in STRIPS:
    parents = [e for e in seeds if e["task_text"].startswith(prefix)]
    assert len(parents) == 1, f"expected 1 parent for {prefix!r}, got {len(parents)}"
    assert stripped not in by_text, f"stripped text collides with a seed: {stripped!r}"
    emit(parents[0], stripped, "WL-2:strip-confirmation",
         risk_level=5, suggested_ppe=[], professional_category=prof,
         followup_questions=[{"field": field, "question": Q[field], "answer": None}])

# ---------------------------------------------------------------- WL-1a
# Conversational rephrasing. Seeds are uniformly bare imperatives; real chat
# input is hedged and question-shaped, so this is genuine robustness
# coverage, not just volume. Content is unchanged -> label inherited.
CONCERN = re.compile(r"^(there|the |my |a |water |sewage |i can )", re.I)

ACTION_PREFIX = [
    "I want to {t}",
    "planning to {t} this weekend",
    "thinking about trying to {t}",
    "can I {t} myself?",
    "is it safe for me to {t}?",
    "I was going to {t} - any reason not to?",
    "how risky is it to {t}?",
]
ACTION_SUFFIX = [
    "{t} - is this something I can handle on my own?",
    "{t}, is that a DIY job?",
    "{t} - do I need to get someone in?",
]
CONCERN_TEMPLATES = [
    "{t} - what should I do?",
    "{t}. is this something I need to worry about?",
    "{t}, how urgent is this?",
    "{t} - can I sort this out myself?",
    "{t}. should I be calling someone?",
]

for i, e in enumerate(seeds):
    t = e["task_text"]
    if CONCERN.match(t):
        tpl = CONCERN_TEMPLATES[i % len(CONCERN_TEMPLATES)]
    elif " - " in t:
        # already has a dash clause; only prefix templates read cleanly
        tpl = ACTION_PREFIX[i % len(ACTION_PREFIX)]
    else:
        pool = ACTION_PREFIX + ACTION_SUFFIX
        tpl = pool[i % len(pool)]
    emit(e, tpl.format(t=t), "WL-1a:rephrase")

# ---------------------------------------------------------------- WL-1b
# Slot substitution, restricted to rooms that carry no safety signal.
# Deliberately excludes bathroom/basement/loft/garage etc, where the room
# itself changes the hazard picture (water, confined space, height).
# "landing" is deliberately excluded: it reads fine attributively ("the
# landing ceiling") but not with in/my ("a wall outlet in the landing").
NEUTRAL = ["bedroom", "hallway", "living room", "dining room", "spare room"]
UNSAFE_TO_SWAP = {"water_damage", "confined_space", "asbestos_exposure"}

swaps = 0
for i, e in enumerate(seeds):
    if set(e["hazards"]) & UNSAFE_TO_SWAP:
        continue
    t = e["task_text"]
    present = [r for r in NEUTRAL if r in t]
    if len(present) != 1:
        continue
    src = present[0]
    dst = [r for r in NEUTRAL if r != src][(i + swaps) % (len(NEUTRAL) - 1)]
    new_text = t.replace(src, dst)
    if new_text in by_text:
        continue
    emit(e, new_text, "WL-1b:room-substitution")
    swaps += 1

# ---------------------------------------------------------------- finalise
seen = set()
deduped = []
for g in generated:
    if g["task_text"] in by_text or g["task_text"] in seen:
        continue
    seen.add(g["task_text"])
    deduped.append(g)

for n, g in enumerate(deduped, 1):
    g["id"] = f"gen-{n:04d}"

OUT.write_text(json.dumps(deduped, indent=2) + "\n", encoding="utf-8")

from collections import Counter
print(f"seeds: {len(seeds)}")
print(f"generated: {len(deduped)}  (dropped {len(generated) - len(deduped)} collisions)")
print(f"  by rule: {dict(Counter(g['generation_rule'] for g in deduped))}")
print(f"  by risk: {dict(sorted(Counter(g['risk_level'] for g in deduped).items()))}")
print(f"TOTAL: {len(seeds) + len(deduped)}")
