#!/usr/bin/env python3
"""Publish a batch to Instagram AND the Facebook Page - one Page token, both.

Facebook-login flow (graph.facebook.com), NOT Gridshift's Instagram-login flow
(graph.instagram.com). The IG-login flow cannot touch a Facebook Page; this one
does both because the IG Business account is linked to the Page.

  python publish_meta.py --whoami                 # sanity-check the token
  python publish_meta.py --dir posts/2026-07-12_1300
  python publish_meta.py --dir ... --ig-only

Secrets come from the environment (GitHub Secrets), never from a committed file:
  META_ACCESS_TOKEN, IG_USER_ID, FB_PAGE_ID, IMAGE_BASE_URL

Instagram does NOT accept a file upload - it fetches the image from a public
https URL. That is why the repo is public and the cards are committed: their
raw.githubusercontent.com URL is the image host.

HARD RULE (learned the expensive way on Gridshift): a green Actions run proves
nothing. This script prints `published ig_media_id=...` / `published fb_post_id=...`
on success and exits non-zero on failure. The workflow greps for those strings.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GRAPH = "https://graph.facebook.com/v21.0"

TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
IMAGE_BASE_URL = os.environ.get("IMAGE_BASE_URL", "").rstrip("/")


def _call(path: str, params: dict, post: bool = False) -> dict:
    # Default to the system-user token, but let a caller pass its own
    # access_token (the Page photo endpoint needs the PAGE token).
    params = {"access_token": TOKEN, **params}
    url = f"{GRAPH}/{path}"
    try:
        if post:
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(url, data=data, method="POST")
        else:
            req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise SystemExit(f"Meta API error {e.code} on {path}: {body}") from e


def whoami() -> None:
    if not TOKEN:
        raise SystemExit("META_ACCESS_TOKEN is not set")
    me = _call("me", {"fields": "id,name"})
    print("token belongs to:", me)
    if IG_USER_ID:
        print("instagram:", _call(IG_USER_ID, {"fields": "id,username,followers_count"}))
    if FB_PAGE_ID:
        print("facebook page:", _call(FB_PAGE_ID, {"fields": "id,name,fan_count"}))


def publish_instagram(image_url: str, caption: str) -> str:
    c = _call(f"{IG_USER_ID}/media",
              {"image_url": image_url, "caption": caption}, post=True)
    cid = c["id"]
    # The container has to finish downloading our image before it can publish.
    for _ in range(12):
        time.sleep(3)
        st = _call(cid, {"fields": "status_code,status"})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise SystemExit(f"IG container error: {st}")
    else:
        raise SystemExit(f"IG container never finished: {cid}")
    return _call(f"{IG_USER_ID}/media_publish", {"creation_id": cid}, post=True)["id"]


_PAGE_TOKEN: dict = {}


def _page_token() -> str:
    """Posting to a Page requires the Page's own access token, not the
    system-user token. Meta's error if you get this wrong is the misleading
    '(#200) publish_actions ... deprecated' - learned on run #1."""
    if "t" not in _PAGE_TOKEN:
        _PAGE_TOKEN["t"] = _call(FB_PAGE_ID, {"fields": "access_token"})["access_token"]
    return _PAGE_TOKEN["t"]


def publish_facebook(image_url: str, caption: str) -> str:
    r = _call(f"{FB_PAGE_ID}/photos",
              {"url": image_url, "caption": caption, "published": "true",
               "access_token": _page_token()}, post=True)
    return r.get("post_id") or r["id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--whoami", action="store_true")
    ap.add_argument("--ig-only", action="store_true")
    ap.add_argument("--fb-only", action="store_true")
    a = ap.parse_args()

    if a.whoami:
        whoami()
        return 0

    for name, val in (("META_ACCESS_TOKEN", TOKEN), ("IG_USER_ID", IG_USER_ID),
                      ("IMAGE_BASE_URL", IMAGE_BASE_URL)):
        if not val:
            raise SystemExit(f"{name} is not set")
    if not a.ig_only and not FB_PAGE_ID:
        raise SystemExit("FB_PAGE_ID is not set (use --ig-only to skip Facebook)")
    if not a.dir:
        raise SystemExit("--dir is required")

    batch = json.loads((Path(a.dir) / "batch.json").read_text(encoding="utf-8"))
    published = 0

    for item in batch:
        image_url = f"{IMAGE_BASE_URL}/{item['image']}"
        print(f"\n-> {item['kind']} {image_url}")
        if not a.fb_only:
            print("published ig_media_id=" + publish_instagram(image_url, item["caption"]))
            published += 1
        if not a.ig_only:
            try:
                print("published fb_post_id=" + publish_facebook(image_url, item["caption"]))
            except SystemExit as e:
                # Never let a Facebook hiccup kill the Instagram half of the
                # batch - but shout, so the log is never quietly green.
                print(f"::warning::facebook publish FAILED: {e}")
        time.sleep(5)

    if published == 0 and not a.fb_only:
        raise SystemExit("published nothing - failing loudly rather than going green")
    print(f"\nDONE: {len(batch)} post(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
