from __future__ import annotations

from dataclasses import dataclass


RISK_LEVELS: dict[int, str] = {
    1: "Safe DIY",
    2: "DIY with supervision",
    3: "Professional recommended",
    4: "Professional required",
    5: "Dangerous / permit-required / do not attempt",
}

MIN_SCORE_BY_LEVEL: dict[int, int] = {
    1: 10,
    2: 25,
    3: 45,
    4: 65,
    5: 85,
}


@dataclass(frozen=True)
class CategoryProfile:
    label: str
    base_score: int
    keywords: tuple[str, ...]


CATEGORY_PROFILES: dict[str, CategoryProfile] = {
    "electrical": CategoryProfile(
        label="Electrical",
        base_score=44,
        keywords=(
            "electrical",
            "wiring",
            "wire",
            "breaker",
            "outlet",
            "socket",
            "switch",
            "ceiling fan",
            "light fixture",
            "exposed wire",
        ),
    ),
    "plumbing": CategoryProfile(
        label="Plumbing",
        base_score=34,
        keywords=(
            "pipe",
            "leak",
            "leaking",
            "tap",
            "faucet",
            "sink",
            "toilet",
            "drain",
            "water heater",
            "water leakage",
            "valve",
        ),
    ),
    "masonry_demolition": CategoryProfile(
        label="Masonry / Demolition",
        base_score=38,
        keywords=(
            "tile",
            "tiles",
            "masonry",
            "brick",
            "concrete",
            "chisel",
            "drill wall",
            "break wall",
            "demolition",
            "remove wall",
        ),
    ),
    "painting": CategoryProfile(
        label="Painting",
        base_score=14,
        keywords=("paint", "painting", "primer", "wall paint", "paint room"),
    ),
    "carpentry": CategoryProfile(
        label="Carpentry / Assembly",
        base_score=20,
        keywords=("shelf", "cabinet", "door", "assemble", "furniture", "wood"),
    ),
    "cleaning": CategoryProfile(
        label="Cleaning",
        base_score=10,
        keywords=("clean", "cleaning", "basic cleaning", "wash"),
    ),
    "roofing": CategoryProfile(
        label="Roofing",
        base_score=58,
        keywords=("roof", "roof repair", "gutter", "scaffold"),
    ),
    "gas": CategoryProfile(
        label="Gas",
        base_score=82,
        keywords=("gas line", "gas pipe", "gas leak", "natural gas", "propane"),
    ),
    "structural": CategoryProfile(
        label="Structural",
        base_score=76,
        keywords=(
            "load-bearing",
            "load bearing",
            "structural beam",
            "support column",
            "foundation",
        ),
    ),
    "general": CategoryProfile(label="General DIY", base_score=22, keywords=()),
}
