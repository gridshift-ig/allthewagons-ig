"""Parse the ATW_WAGONS object out of wagons-database.html into wagons.json.

The database is a JS literal, not JSON (unquoted keys, en-dash year ranges), so
this is a targeted parser, not json.loads. Output feeds the evergreen
"wagon of the day" cards.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

FIELD = re.compile(
    r'model:\s*"(?P<model>[^"]*)"\s*,\s*'
    r'years:\s*"(?P<years>[^"]*)"\s*,\s*'
    r'(?:imp:\s*\d+\s*,\s*)?'          # optional "imp" (import-only) flag
    r'hp:\s*(?P<hp>[\d.]+|null)\s*,\s*'
    r'tq:\s*(?P<tq>[\d.]+|null)\s*,\s*'
    r'w:\s*(?P<w>[\d.]+|null)\s*,\s*'
    r'len:\s*(?P<len>[\d.]+|null)\s*,\s*'
    r'ht:\s*(?P<ht>[\d.]+|null)\s*,\s*'
    r'msrp:\s*"(?P<msrp>[^"]*)"\s*,\s*'
    r's060:\s*"(?P<s060>[^"]*)"',
    re.S,
)
IMG = re.compile(r'img:\s*"([^"]*)"')
APRX = re.compile(r'aprx:\s*\[([^\]]*)\]')
MAKE = re.compile(r'^\s*"([^"]+)":\s*\[', re.M)


def parse(html: str):
    start = html.index("const ATW_WAGONS")
    body = html[start:]
    makes = [(m.start(), m.group(1)) for m in MAKE.finditer(body)]
    wagons = []
    for i, (pos, make) in enumerate(makes):
        end = makes[i + 1][0] if i + 1 < len(makes) else len(body)
        block = body[pos:end]
        # split into per-model entries so img/aprx bind to the right model
        for entry in re.split(r"\n\s*\{", block)[1:]:
            m = FIELD.search(entry)
            if not m:
                continue
            d = m.groupdict()
            img = IMG.search(entry)
            aprx = APRX.search(entry)
            approx = re.findall(r'"([^"]+)"', aprx.group(1)) if aprx else []
            wagons.append({
                "make": make,
                "model": d["model"],
                "years": d["years"].replace("–", "-"),
                "hp": None if d["hp"] == "null" else int(float(d["hp"])),
                "tq": None if d["tq"] == "null" else int(float(d["tq"])),
                "weight_lb": None if d["w"] == "null" else int(float(d["w"])),
                "length_in": None if d["len"] == "null" else float(d["len"]),
                "height_in": None if d["ht"] == "null" else float(d["ht"]),
                "msrp": d["msrp"],
                "s060": d["s060"],
                "approx": approx,
                "img": img.group(1) if img else None,
            })
    return wagons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="wagons-database.html")
    ap.add_argument("--out", default="wagons.json")
    a = ap.parse_args()
    html = Path(a.source).read_text(encoding="utf-8", errors="replace")
    wagons = parse(html)
    Path(a.out).write_text(json.dumps(wagons, indent=1), encoding="utf-8")
    makes = sorted({w["make"] for w in wagons})
    with_img = sum(1 for w in wagons if w["img"])
    print(f"{len(wagons)} wagons / {len(makes)} makes / {with_img} with a Commons image")
    print("makes:", ", ".join(makes))


if __name__ == "__main__":
    main()
