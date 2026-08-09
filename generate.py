#!/usr/bin/env python3
"""Build a batch of AllTheWagons Instagram/Facebook cards.

  python generate.py                # default batch
  python generate.py --count 3
  python generate.py --no-photos    # text-only cards (the copyright kill switch)
  python generate.py --dry-run      # pick + caption, render nothing

Writes posts/<UTC timestamp>/post_N.jpg + post_N.txt (caption) + batch.json.
Runs on the GitHub Actions runner, which HAS network. Claude's sandbox does not.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from wagons import feeds, select
from wagons.cards import render_evergreen_card, render_news_card
from wagons.caption import evergreen_caption, news_caption
from wagons.commons import licence

ROOT = Path(__file__).resolve().parent
THEME = "dark"
UA = "Mozilla/5.0 (AllTheWagonsBot/1.0; +https://allthewagons.com)"
SKIPPED_PATH = ROOT / "skipped.json"


def big_commons(url: str) -> str:
    """Commons stores a 500px thumb in the database. Ask for 1280px instead -
    500px upscaled to a 1080 card looks soft.

    Two URL shapes appear in wagons.json: the .../thumb/.../500px-Foo.jpg path
    form, and the Special:FilePath/Foo.jpg?width=500 query-param form. Handle
    both so the width bump actually applies to Special:FilePath entries too."""
    if "Special:FilePath" in url:
        return re.sub(r"([?&])width=\d+", r"\g<1>width=1280", url)
    return re.sub(r"/\d+px-", "/1280px-", url)


def spec_row(w: dict) -> list[tuple[str, str]]:
    """The card shows 3 stats. Build them from the database fields, marking any
    value the database flagged as approximate with a leading ~."""
    ap = set(w.get("approx") or [])
    out = []
    if w.get("hp"):
        out.append(("Power", f"{'~' if 'hp' in ap else ''}{w['hp']} hp"))
    if w.get("s060"):
        out.append(("0-60", f"{w['s060']} s"))
    if w.get("tq"):
        out.append(("Torque", f"{'~' if 'tq' in ap else ''}{w['tq']} lb-ft"))
    if len(out) < 3 and w.get("weight_lb"):
        out.append(("Weight", f"{'~' if 'w' in ap else ''}{w['weight_lb']:,} lb"))
    return out[:3]


def download(url: str, dest: Path) -> Path | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r, dest.open("wb") as f:
            shutil.copyfileobj(r, f)
        return dest if dest.stat().st_size > 5000 else None
    except Exception as e:  # noqa: BLE001 - no photo is survivable; a crash is not
        print(f"  photo download failed ({type(e).__name__})")
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--no-photos", action="store_true",
                    help="text-only cards; the copyright kill switch")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    wagons = json.loads((ROOT / "wagons.json").read_text(encoding="utf-8"))
    stories = feeds.fetch_all(ROOT / "feeds.json")
    picked = select.pick(stories, wagons, a.count)
    if not picked:
        print("NOTHING TO POST")
        return 1

    run = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    out = ROOT / "posts" / run
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "_src"
    tmp.mkdir(exist_ok=True)

    batch = []
    skipped: list[dict] = []
    for i, p in enumerate(picked, 1):
        jpg, txt = out / f"post_{i}.jpg", out / f"post_{i}.txt"

        if p["kind"] == "news":
            # The publisher's own share-card image, baked into our card.
            # Scott's explicit call - see PROJECT-NOTES. --no-photos reverts it.
            if not a.no_photos:
                url = p.get("img") or feeds.og_image(p["link"])
                if url:
                    p["bg_image"] = str(download(url, tmp / f"n{i}.jpg") or "")
            cap = news_caption(p)
            print(f"[{i}] NEWS  {p['source']}: {p['title'][:70]}")
            if not a.dry_run:
                render_news_card(p, jpg, THEME)
        else:
            # Evergreen photos are Wikimedia Commons - check the licence, print
            # the credit ON the card. --no-photos is the deliberate text-only
            # kill switch and is never a skip. But when a photo IS expected and
            # can't be verified, DO NOT silently fall back to a text-only card -
            # that's exactly how 57 "Wagon of the Day" models (every Special:
            # FilePath entry in wagons.json) quietly posted broken cards for
            # weeks with nobody noticing. Skip the post instead and raise it.
            p["specs"] = spec_row(p)
            skip_reason = None
            if a.no_photos:
                pass  # intentional text-only mode, not a failure
            elif not p.get("img"):
                skip_reason = "no image URL in wagons.json"
            else:
                lic = licence(p["img"])
                if lic and lic["ok"]:
                    got = download(big_commons(p["img"]), tmp / f"e{i}.jpg")
                    if not got:                       # 1280px may not exist
                        got = download(p["img"], tmp / f"e{i}.jpg")
                    if got:
                        p["bg_image"] = str(got)
                        p["credit"] = lic["credit"]
                    else:
                        skip_reason = "licensed photo failed to download"
                elif lic:
                    skip_reason = f"licence not usable ({lic['licence']})"
                else:
                    skip_reason = "licence unverifiable (Commons lookup failed)"

            if skip_reason:
                print(f"[{i}] SKIP  {p['make']} {p['model']}: {skip_reason}")
                print(f"::error::Wagon of the Day skipped - {p['make']} {p['model']} "
                      f"({p.get('years', '')}): {skip_reason}")
                skipped.append({"make": p["make"], "model": p["model"],
                                 "years": p.get("years", ""), "reason": skip_reason})
                continue

            cap = evergreen_caption(p)
            tag = " + photo" if p.get("bg_image") else " (text, --no-photos)"
            print(f"[{i}] WAGON {p['make']} {p['model']}{tag}")
            if not a.dry_run:
                render_evergreen_card(p, jpg, THEME)

        if not a.dry_run:
            txt.write_text(cap, encoding="utf-8")
        batch.append({"n": i, "kind": p["kind"], "image": f"posts/{run}/post_{i}.jpg",
                      "caption": cap})

    if a.dry_run:
        print("\n--- dry run, nothing written ---")
        return 0

    shutil.rmtree(tmp, ignore_errors=True)

    if skipped:
        SKIPPED_PATH.write_text(json.dumps(skipped, indent=1), encoding="utf-8")
        print(f"\n::warning::{len(skipped)} pick(s) skipped this run - see skipped.json")

    # Every pick (skipped or not) is remembered so a still-broken entry (bad
    # licence, dead link) doesn't get re-selected and re-alerted every run.
    select.remember(picked)

    if not batch:
        print(f"\nNOTHING TO POST - all {len(picked)} pick(s) skipped (no verified photo)")
        return 1

    (out / "batch.json").write_text(json.dumps(batch, indent=1), encoding="utf-8")
    print(f"\nwrote {len(batch)} posts -> {out}")
    print(f"::set-run-dir::posts/{run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
