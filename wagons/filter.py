"""Wagon detection. Ported VERBATIM from scripts/update_news.py.

This is the single most important file in the repo: it is what stops the account
posting SUVs. Matching the description as well as the title was tried on the
website and produced garbage - a Polestar 4 SUV, a RUF Porsche and a Mercedes
CLA45 EV all slipped through because the body copy mentioned an estate or a
shooting brake somewhere. HEADLINE ONLY. Fewer + correct beats more + wrong.

If you change this file, change scripts/update_news.py in the Wagons repo too -
they are meant to agree.
"""
from __future__ import annotations

import re

WAGON_TERMS = [
    "wagon", "wagons", "estate", "estate car", "avant", "touring", "shooting brake",
    "sportwagen", "sport wagen", "sportbrake", "allroad", "alltrack", "outback",
    "cross country", "variant", "caravan", "longroof", "long roof", "station wagon",
    # Porsche's wagon-ish bodystyles. "porsche" was already in CAR_CONTEXT below
    # for these, but the TERMS list never actually contained them - so every
    # Taycan Cross Turismo / Panamera Sport Turismo story was being silently
    # dropped. Found by tests/test_filter.py. Same bug exists in the website's
    # scripts/update_news.py - fix it there too.
    "cross turismo", "sport turismo",
]

# "touring"/"caravan"/"variant"/"estate" are noisy on their own - they need a car
# brand or model in the headline before they count.
AMBIGUOUS = {"touring", "caravan", "variant", "estate"}
CAR_CONTEXT = ["bmw", "m5", "5 series", "3 series", "dodge", "vw", "volkswagen", "golf",
               "audi", "mercedes", "volvo", "porsche", "wagon", "estate"]

# Checked BEFORE the wagon-term match. "porsche" is legitimately in CAR_CONTEXT
# (Taycan Cross Turismo, Panamera Sport Turismo), so "touring" + "porsche" would
# otherwise pass the AMBIGUOUS gate - but the 911 GT3 Touring is a coupe.
EXCLUDE_TERMS = ["gt3 touring"]

EXCLUDE_RE = [re.compile(r"\b" + re.escape(t) + r"\b", re.I) for t in EXCLUDE_TERMS]
WAGON_RE = [(t, re.compile(r"\b" + re.escape(t) + r"\b", re.I)) for t in WAGON_TERMS]


def is_wagon(title: str) -> bool:
    """True only if a wagon term appears in the HEADLINE."""
    t = (title or "").lower()
    if any(rx.search(t) for rx in EXCLUDE_RE):
        return False
    for term, rx in WAGON_RE:
        if rx.search(t):
            if term in AMBIGUOUS and not any(c in t for c in CAR_CONTEXT):
                continue
            return True
    return False
