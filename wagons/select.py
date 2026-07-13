"""Pick what to post: fresh wagon news first, evergreen database cards to fill.

Wagon news is thin - a live run over 14 feeds found ~5 genuine wagon stories out
of 387. So the evergreen picker does most of the work, and that is by design.
Nothing repeats until the pool is exhausted (posted.json is the memory).
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

from .filter import is_wagon

HISTORY = Path("posted.json")
NEWS_MAX_AGE_DAYS = 4


def _history() -> dict:
    if HISTORY.exists():
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    return {"news": [], "evergreen": []}


def _save(h: dict) -> None:
    HISTORY.write_text(json.dumps(h, indent=1), encoding="utf-8")


def pick(stories: list[dict], wagons: list[dict], count: int) -> list[dict]:
    h = _history()
    posted_links = set(h["news"])
    posted_wagons = set(h["evergreen"])
    cutoff = time.time() - NEWS_MAX_AGE_DAYS * 86400

    # 1. fresh wagon news, newest first, one per source so no outlet dominates
    news, seen_sources = [], set()
    for s in stories:
        if not is_wagon(s["title"]) or s["link"] in posted_links or s["ts"] < cutoff:
            continue
        if s["source"] in seen_sources:
            continue
        seen_sources.add(s["source"])
        s["kind"] = "news"
        news.append(s)

    picked = news[:count]

    # 2. backfill with evergreen database cards
    if len(picked) < count:
        pool = [w for w in wagons if f"{w['make']}|{w['model']}" not in posted_wagons]
        if not pool:                       # whole database posted - start over
            print("evergreen pool exhausted; resetting")
            posted_wagons = set()
            pool = list(wagons)
        random.shuffle(pool)
        for w in pool[: count - len(picked)]:
            w = dict(w)
            w["kind"] = "evergreen"
            picked.append(w)

    print(f"picked {sum(1 for p in picked if p['kind'] == 'news')} news + "
          f"{sum(1 for p in picked if p['kind'] == 'evergreen')} evergreen")
    return picked


def remember(picked: list[dict]) -> None:
    h = _history()
    for p in picked:
        if p["kind"] == "news":
            h["news"].append(p["link"])
        else:
            h["evergreen"].append(f"{p['make']}|{p['model']}")
    h["news"] = h["news"][-500:]
    _save(h)
