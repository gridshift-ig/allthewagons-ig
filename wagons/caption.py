"""Caption + hashtag builder. Deterministic - no LLM, no API key."""
from __future__ import annotations

import re

SITE = "allthewagons.com"

BASE_TAGS = ["#wagon", "#stationwagon", "#estatecar", "#longroof", "#allthewagons"]

BRAND_TAGS = {
    "audi": "#audi", "rs6": "#rs6avant", "avant": "#avant",
    "bmw": "#bmw", "touring": "#bmwtouring", "m5": "#m5touring",
    "mercedes": "#mercedesbenz", "amg": "#amg",
    "volvo": "#volvo", "v60": "#v60", "v90": "#v90",
    "subaru": "#subaru", "outback": "#outback", "levorg": "#levorg",
    "porsche": "#porsche", "taycan": "#taycan",
    "volkswagen": "#vw", "golf": "#golfr", "vw": "#vw",
    "jaguar": "#jaguar", "cadillac": "#cadillac", "cts-v": "#ctsvwagon",
    "electric": "#ev", "ev": "#ev", "hybrid": "#hybrid",
}

MAX_TAGS = 12


def _tags(text: str) -> list[str]:
    t = text.lower()
    tags = list(BASE_TAGS)
    for kw, tag in BRAND_TAGS.items():
        if re.search(r"\b" + re.escape(kw) + r"\b", t) and tag not in tags:
            tags.append(tag)
    return tags[:MAX_TAGS]


def news_caption(story: dict) -> str:
    body = (
        f"{story['title']}\n\n"
        f"Via {story['source']}. Full story linked in bio - we summarise and link out, "
        f"we don't republish.\n\n"
        f"More wagon news, reviews and the full database at {SITE}\n\n"
    )
    return body + " ".join(_tags(story["title"]))


def evergreen_caption(w: dict) -> str:
    specs = []
    if w.get("hp"):
        specs.append(f"{w['hp']} hp")
    if w.get("tq"):
        specs.append(f"{w['tq']} lb-ft")
    if w.get("s060"):
        specs.append(f"0-60 in {w['s060']}s")
    if w.get("weight_lb"):
        specs.append(f"{w['weight_lb']:,} lb")
    line = " | ".join(specs)

    approx = ""
    if w.get("approx"):
        approx = "\n\nSome figures are approximate - see the database for what's sourced."

    credit = f"\n\n{w['credit']}" if w.get("credit") else ""

    body = (
        f"{w['make']} {w['model']} ({w['years']})\n\n"
        f"{line}{approx}\n\n"
        f"One of 139 wagons in our database - specs, years and reviews for every one. "
        f"Link in bio.{credit}\n\n"
    )
    return body + " ".join(_tags(f"{w['make']} {w['model']}"))
