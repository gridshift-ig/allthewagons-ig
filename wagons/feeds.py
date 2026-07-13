"""Fetch + parse RSS and Atom feeds. Stdlib only.

Adapted from the Wagons site's scripts/update_news.py (same parser, same
gzip/Atom handling). Dead or blocked feeds are skipped, never fatal.
"""
from __future__ import annotations

import gzip
import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

UA = "Mozilla/5.0 (AllTheWagonsBot/1.0; +https://allthewagons.com)"
TIMEOUT = 20


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        "Accept-Encoding": "gzip",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", s or ""))).strip()


def _cdata(s: str) -> str:
    return re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s or "", flags=re.S)


def _tag(block: str, name: str) -> str:
    m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", block, re.S | re.I)
    return _cdata(m.group(1)).strip() if m else ""


def _date(block: str):
    raw = _tag(block, "pubDate") or _tag(block, "published") or _tag(block, "updated")
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _feed_image(block: str) -> str:
    for pat in (
        r'<media:thumbnail[^>]*\burl="([^"]+)"',
        r'<media:content[^>]*\burl="([^"]+)"',
        r'<enclosure[^>]*\burl="([^"]+)"[^>]*type="image',
        r'<enclosure[^>]*type="image[^"]*"[^>]*\burl="([^"]+)"',
    ):
        m = re.search(pat, block, re.I)
        if m:
            return html.unescape(m.group(1))
    content = html.unescape(_tag(block, "content:encoded") or _tag(block, "description"))
    m = re.search(r'<img[^>]*\bsrc="([^"]+)"', content, re.I)
    return html.unescape(m.group(1)) if m else ""


def og_image(url: str) -> str:
    """The publisher's own share-card image, from the article's og:image."""
    try:
        page = http_get(url)
    except Exception:  # noqa: BLE001 - an image is nice-to-have, never fatal
        return ""
    for pat in (
        r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
        r'<meta[^>]+content="([^"]+)"[^>]+property="og:image"',
        r'<meta[^>]+name="twitter:image"[^>]+content="([^"]+)"',
    ):
        m = re.search(pat, page, re.I)
        if m:
            return html.unescape(m.group(1).strip())
    return ""


def parse(xml: str, source: str) -> list[dict]:
    is_atom = bool(re.search(r"<feed[\s>]", xml)) and not re.search(r"<rss[\s>]", xml)
    pattern = r"<entry[\s>].*?</entry>" if is_atom else r"<item[\s>].*?</item>"
    out = []
    for block in re.findall(pattern, xml, re.S | re.I):
        title = _strip(_tag(block, "title"))
        if is_atom:
            m = (re.search(r'<link[^>]*rel="alternate"[^>]*href="([^"]+)"', block, re.I)
                 or re.search(r'<link[^>]*href="([^"]+)"', block, re.I))
            link = html.unescape(m.group(1)) if m else ""
        else:
            link = _tag(block, "link")
        if not title or not link:
            continue
        dt = _date(block)
        out.append({
            "source": source,
            "title": title,
            "link": link.strip(),
            "ts": dt.timestamp() if dt else 0,
            "img": _feed_image(block),
        })
    return out


def fetch_all(feeds_path="feeds.json") -> list[dict]:
    cfg = json.loads(Path(feeds_path).read_text(encoding="utf-8"))
    items, skipped = [], []
    for f in cfg["feeds"]:
        if not f.get("enabled", True):
            continue
        try:
            items += parse(http_get(f["url"]), f["name"])
        except Exception as e:  # noqa: BLE001 - a dead feed must never kill the run
            skipped.append(f"{f['name']}: {type(e).__name__}")
    if skipped:
        print("skipped feeds:", "; ".join(skipped))
    # de-dupe by link
    seen, uniq = set(), []
    for it in sorted(items, key=lambda x: -x["ts"]):
        if it["link"] in seen:
            continue
        seen.add(it["link"])
        uniq.append(it)
    print(f"fetched {len(uniq)} unique stories")
    return uniq
