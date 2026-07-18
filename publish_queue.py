#!/usr/bin/env python3
"""Publish the next unposted evergreen card from social-queue.json to the
Facebook Page (and optionally Instagram) via the Meta Graph API.

Why this exists: Facebook's WEB composer actively resists automation — it
recreates its file <input> so a programmatically attached file is discarded,
so the composer never opens. The Graph API is the only reliable path.

Secrets come from the environment (GitHub Secrets), never a committed file:
  META_ACCESS_TOKEN, FB_PAGE_ID, IMAGE_BASE_URL   (IG_USER_ID optional)

  python publish_queue.py                # post the next unposted item
  python publish_queue.py --id newsletter# post a specific item
  python publish_queue.py --ig           # also post it to Instagram
  python publish_queue.py --dry-run      # show what would post
"""
from __future__ import annotations
import argparse, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

GRAPH = "https://graph.facebook.com/v21.0"
TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
IMAGE_BASE_URL = os.environ.get("IMAGE_BASE_URL", "").rstrip("/")
QUEUE = Path(__file__).with_name("social-queue.json")


def _call(path: str, params: dict, post: bool = False) -> dict:
    params = {"access_token": TOKEN, **params}
    url = f"{GRAPH}/{path}"
    try:
        if post:
            req = urllib.request.Request(url, data=urllib.parse.urlencode(params).encode(), method="POST")
        else:
            req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Meta API error {e.code} on {path}: {e.read().decode(errors='replace')}") from e


_PAGE_TOKEN: dict = {}


def _page_token() -> str:
    """Posting to a Page needs the PAGE's own token, not the user/system token.
    Meta's error when you get this wrong is the misleading
    '(#200) publish_actions ... deprecated'."""
    if "t" not in _PAGE_TOKEN:
        _PAGE_TOKEN["t"] = _call(FB_PAGE_ID, {"fields": "access_token"})["access_token"]
    return _PAGE_TOKEN["t"]


def publish_facebook(image_url: str, caption: str) -> str:
    r = _call(f"{FB_PAGE_ID}/photos",
              {"url": image_url, "caption": caption, "published": "true",
               "access_token": _page_token()}, post=True)
    return r.get("post_id") or r["id"]


def publish_instagram(image_url: str, caption: str) -> str:
    c = _call(f"{IG_USER_ID}/media", {"image_url": image_url, "caption": caption}, post=True)
    cid = c["id"]
    for _ in range(12):
        time.sleep(3)
        st = _call(cid, {"fields": "status_code"})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise SystemExit(f"IG container error: {st}")
    else:
        raise SystemExit(f"IG container never finished: {cid}")
    return _call(f"{IG_USER_ID}/media_publish", {"creation_id": cid}, post=True)["id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id")
    ap.add_argument("--ig", action="store_true", help="also post to Instagram")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    items = json.loads(QUEUE.read_text(encoding="utf-8"))
    if a.id:
        pick = next((i for i in items if i["id"] == a.id), None)
        if not pick:
            raise SystemExit(f"no queue item with id={a.id}")
    else:
        pick = next((i for i in items if not i.get("posted")), None)
        if not pick:
            # everything posted once -> start the rotation again
            for i in items:
                i["posted"] = False
            pick = items[0]
            print("queue exhausted - recycling from the top")

    image_url = f"{IMAGE_BASE_URL}/{pick['image']}"
    print(f"-> {pick['id']}  {image_url}")

    if a.dry_run:
        print("DRY RUN - nothing posted")
        print(pick["caption"][:280])
        return 0

    for name, val in (("META_ACCESS_TOKEN", TOKEN), ("FB_PAGE_ID", FB_PAGE_ID),
                      ("IMAGE_BASE_URL", IMAGE_BASE_URL)):
        if not val:
            raise SystemExit(f"{name} is not set")

    print("published fb_post_id=" + publish_facebook(image_url, pick["caption"]))
    if a.ig and IG_USER_ID:
        print("published ig_media_id=" + publish_instagram(image_url, pick["caption"]))

    pick["posted"] = True
    QUEUE.write_text(json.dumps(items, indent=2), encoding="utf-8")
    print("queue updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
