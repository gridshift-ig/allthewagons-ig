"""Wikimedia Commons licence gate for the evergreen card photos.

The wagon database stores a Commons thumbnail URL for every model. Commons is
mostly CC, but NOT uniformly - some files are non-commercial or no-derivatives,
which we must not use. So before a photo goes on a card we ask the Commons API
for that file's licence and author, reject anything NC/ND/unfree, and build the
credit line that then gets PRINTED ON THE IMAGE. Removing that credit voids the
licence - do not "clean up" the card by dropping it.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = "AllTheWagonsBot/1.0 (https://allthewagons.com)"
TIMEOUT = 20

# Substrings that mean "we cannot use this commercially / cannot adapt it".
BLOCKED = ("nc", "nd", "noncommercial", "non-commercial", "noderiv", "fair use", "fairuse")
ALLOWED_PREFIXES = ("cc0", "cc-by", "cc by", "public domain", "pd-", "pd ")


def file_from_url(url: str) -> str:
    """upload.wikimedia.org/.../thumb/a/ab/Foo.jpg/500px-Foo.jpg -> File:Foo.jpg"""
    m = re.search(r"/commons/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/]+)", url)
    if not m:
        return ""
    return "File:" + urllib.parse.unquote(m.group(1))


def _api(params: dict) -> dict:
    q = urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def licence(url: str) -> dict | None:
    """Return {credit, licence, author, ok} or None if we can't verify it.

    ok=False means the licence is present but unusable (NC/ND). Callers must
    fall back to a text-only card - never post an unverified photo.
    """
    title = file_from_url(url)
    if not title:
        return None
    try:
        data = _api({
            "action": "query", "titles": title,
            "prop": "imageinfo", "iiprop": "extmetadata",
        })
    except Exception:  # noqa: BLE001 - never fatal; caller falls back to text card
        return None

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0].get("extmetadata", {})
        if not info:
            continue
        short = (info.get("LicenseShortName", {}).get("value") or "").strip()
        author = re.sub(r"<[^>]+>", "", info.get("Artist", {}).get("value") or "").strip()
        author = re.sub(r"\s+", " ", author)[:40] or "Wikimedia Commons"
        low = short.lower()

        usable = (any(low.startswith(p) for p in ALLOWED_PREFIXES)
                  and not any(b in low.replace("-", " ").split() for b in ("nc", "nd")))
        if any(b in low for b in ("noncommercial", "non-commercial", "noderiv", "fair use")):
            usable = False
        if not short:
            return None

        return {
            "ok": usable,
            "licence": short,
            "author": author,
            "credit": f"Photo: {author} / {short}",
        }
    return None
