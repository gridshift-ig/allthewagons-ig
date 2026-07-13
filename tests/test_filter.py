"""Regression tests for the wagon filter - these are the exact stories that got
through on the website before the headline-only fix. If any of these flip, the
account starts posting SUVs.

Run: python -m tests.test_filter
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wagons.filter import is_wagon  # noqa: E402

MUST_PASS = [
    "Is The New BMW 3 Series Touring Coming To The US? It's Complicated",
    "2025 Audi RS6 Avant Performance review",
    "The Volvo V60 Cross Country is the last honest wagon",
    "BMW M5 Touring first drive",
    "Mercedes E-Class Estate gets a facelift",
    "VW Golf Variant spied testing",
    "Porsche Taycan Cross Turismo gets more range",
    "Audi A6 Allroad returns to the US",
    "Subaru Outback goes rugged",
    "This shooting brake is the coolest thing at the show",
]

MUST_FAIL = [
    # Real false positives caught on the live site:
    "Porsche 911 GT3 Touring is the purist's 911",   # coupe trim, not a wagon
    "Polestar 4 review: the SUV with no rear window",
    "RUF turns the 911 into something wilder",
    "Mercedes CLA45 EV breaks cover",
    # Generic non-wagon car news:
    "Ferrari announces a new V12",
    "Tesla cuts Model Y prices again",
    "The Caravan of Courage: a Star Wars retrospective",  # 'caravan', no car context
]


def main():
    bad = []
    for t in MUST_PASS:
        if not is_wagon(t):
            bad.append(("FALSE NEGATIVE", t))
    for t in MUST_FAIL:
        if is_wagon(t):
            bad.append(("FALSE POSITIVE", t))
    for kind, t in bad:
        print(f"FAIL [{kind}] {t}")
    print(f"{len(MUST_PASS) + len(MUST_FAIL) - len(bad)}/"
          f"{len(MUST_PASS) + len(MUST_FAIL)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
