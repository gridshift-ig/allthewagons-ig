"""AllTheWagons 1080x1080 Instagram card renderer.

Card types:
  - news      : a wagon news headline + source. Text only - we have no rights
                to publishers' photos.
  - evergreen : a "wagon of the day" card from the wagon database. May carry a
                LICENSED photo in a band, with the credit printed on the image.

NEVER put emoji in a rendered card - the fonts have no emoji glyphs (tofu).
No pills/bubbles: section labels are plain text with a short accent rule.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SIZE = 1080

THEMES = {
    "light": {
        "key": "light",
        "bg_top": (255, 255, 255),
        "bg_bottom": (238, 240, 243),
        "accent": (227, 22, 30),
        "ink": (18, 20, 24),
        "muted": (110, 118, 130),
        "rule": (222, 226, 232),
        "logo_color": (18, 20, 24),
    },
    "dark": {
        "key": "dark",
        "bg_top": (20, 23, 26),
        "bg_bottom": (12, 14, 16),
        "accent": (76, 184, 144),
        "ink": (255, 255, 255),
        "muted": (150, 160, 168),
        "rule": (44, 50, 56),
        "logo_color": (255, 255, 255),
    },
}

WORDMARK = "ALLTHEWAGONS.COM"
DB_COUNT = 139          # keep in sync with wagons.json / the site trust bar
TAGLINE = "WAGON NEWS - REVIEWS - THE DATABASE"
LOGO_SRC = ROOT.parent / "images" / "logo-light.png"

_FONT_CANDIDATES = {
    "bold": ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "C:/Windows/Fonts/arialbd.ttf"],
    "semibold": ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "C:/Windows/Fonts/arialbd.ttf"],
    "regular": ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "C:/Windows/Fonts/arial.ttf"],
}


def _font(kind, size):
    for path in _FONT_CANDIDATES[kind]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _gradient(top, bottom):
    base = Image.new("RGB", (SIZE, SIZE), top)
    grad = Image.new("L", (1, SIZE))
    for y in range(SIZE):
        grad.putpixel((0, y), int(255 * (y / SIZE) ** 1.5))
    grad = grad.resize((SIZE, SIZE))
    return Image.composite(Image.new("RGB", (SIZE, SIZE), bottom), base, grad)


def _logo(color, height):
    if not LOGO_SRC.exists():
        return None
    src = Image.open(LOGO_SRC).convert("RGBA")
    w, h = src.size
    src = src.resize((max(1, int(w * height / h)), height), Image.LANCZOS)
    tint = Image.new("RGBA", src.size, tuple(color) + (255,))
    tint.putalpha(src.split()[3])
    return tint


def _photo_band(canvas, path, y0, y1):
    """Cover-crop a photo into a horizontal band. Text never sits on it."""
    band_w, band_h = SIZE, y1 - y0
    img = Image.open(path).convert("RGB")
    w, h = img.size
    scale = max(band_w / w, band_h / h)
    img = img.resize((int(w * scale + 0.5), int(h * scale + 0.5)), Image.LANCZOS)
    w, h = img.size
    left = (w - band_w) // 2
    top = int((h - band_h) * 0.45)
    canvas.paste(img.crop((left, top, left + band_w, top + band_h)), (0, y0))


def _fit(draw, text, kind, max_width, start, minimum, max_lines=5):
    for size in range(start, minimum - 1, -3):
        font = _font(kind, size)
        avg = draw.textlength("ABCDEFGHIJ abcdefghij", font=font) / 21
        lines = textwrap.wrap(text, width=max(8, int(max_width / avg)))
        if len(lines) <= max_lines:
            widest = max((draw.textlength(l, font=font) for l in lines), default=0)
            if widest <= max_width:
                return font, lines, size
    return _font(kind, minimum), textwrap.wrap(text, width=22)[:max_lines + 1], minimum


def _header(canvas, d, t, M):
    d.rectangle([0, 0, SIZE, 14], fill=t["accent"])
    logo = _logo(t["logo_color"], 62)
    if logo:
        canvas.paste(logo, (M, 54), logo)
        ty = 54 + 62 + 12
    else:
        d.text((M, 58), WORDMARK, font=_font("bold", 46), fill=t["ink"])
        ty = 118
    d.text((M, ty), TAGLINE, font=_font("semibold", 19), fill=t["muted"])


def _kicker(d, t, M, label, y):
    """Plain-text section label with a short accent rule above it. No pills."""
    d.rectangle([M, y, M + 64, y + 5], fill=t["accent"])
    d.text((M, y + 20), label, font=_font("bold", 27), fill=t["accent"])
    return y + 62


def _footer(d, t, M, primary, secondary, credit=None):
    d.rectangle([M, SIZE - 156, M + 88, SIZE - 150], fill=t["accent"])
    d.text((M, SIZE - 130), primary, font=_font("semibold", 29), fill=t["ink"])
    d.text((M, SIZE - 88), secondary, font=_font("regular", 19), fill=t["muted"])
    if credit:
        # CC BY-SA REQUIRES the credit on the image itself. Do not remove.
        cf = _font("regular", 17)
        cw = d.textlength(credit, font=cf)
        d.text((SIZE - M - cw, SIZE - 86), credit, font=cf, fill=t["muted"])


def render_news_card(story, out_path, theme="light"):
    """story = {title, source, bg_image (optional), url}

    If bg_image is present it is placed in a photo band with a
    "Photo: <source>" credit. See PROJECT-NOTES - using the publisher's own
    RSS/og:image on a card we publish is Scott's explicit call, and it is a
    knowingly-accepted copyright risk (hosting a copy != hotlinking).
    """
    t = THEMES[theme]
    M = 80
    photo = bool(story.get("bg_image")) and Path(story["bg_image"]).exists()

    canvas = _gradient(t["bg_top"], t["bg_bottom"])
    d = ImageDraw.Draw(canvas)
    _header(canvas, d, t, M)

    src = "VIA " + story["source"].upper()
    bf = _font("semibold", 25)
    d.text((SIZE - M - d.textlength(src, font=bf), 74), src, font=bf, fill=t["muted"])

    if photo:
        BAND_TOP, BAND_BOT = 190, 545
        _photo_band(canvas, story["bg_image"], BAND_TOP, BAND_BOT)
        d = ImageDraw.Draw(canvas)
        d.rectangle([0, BAND_BOT, SIZE, BAND_BOT + 5], fill=t["accent"])
        ky = _kicker(d, t, M, story.get("ribbon", "WAGON NEWS"), y=BAND_BOT + 34)
        start, minimum, max_lines = 54, 34, 3
    else:
        ky = _kicker(d, t, M, story.get("ribbon", "WAGON NEWS"), y=300)
        start, minimum, max_lines = 76, 42, 5

    font, lines, size = _fit(d, story["title"], "bold", SIZE - 2 * M,
                             start, minimum, max_lines=max_lines)
    lh = int(size * 1.16)
    y = ky if photo else max(400, SIZE - 300 - lh * len(lines))
    for ln in lines:
        d.text((M, y), ln, font=font, fill=t["ink"])
        y += lh

    credit = ("Photo: " + story["source"]) if photo else None
    _footer(d, t, M, "Full story - link in bio",
            "Summary only - original article belongs to the source", credit=credit)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "JPEG", quality=92)
    return out_path


def render_evergreen_card(wagon, out_path, theme="light"):
    """wagon = {make, model, years, specs: [(label, value)], bg_image, credit}

    Layout: brand header (solid) / optional photo band / spec panel (solid).
    """
    t = THEMES[theme]
    M = 80
    photo = bool(wagon.get("bg_image")) and Path(wagon["bg_image"]).exists()

    canvas = _gradient(t["bg_top"], t["bg_bottom"])
    d = ImageDraw.Draw(canvas)
    _header(canvas, d, t, M)

    if photo:
        BAND_TOP, BAND_BOT = 190, 545
        _photo_band(canvas, wagon["bg_image"], BAND_TOP, BAND_BOT)
        d = ImageDraw.Draw(canvas)
        d.rectangle([0, BAND_BOT, SIZE, BAND_BOT + 5], fill=t["accent"])
        content_top = BAND_BOT + 34
    else:
        content_top = 300

    ky = _kicker(d, t, M, wagon.get("ribbon", "WAGON OF THE DAY"), y=content_top)

    d.text((M, ky), wagon["make"].upper(), font=_font("semibold", 30), fill=t["muted"])
    font, lines, size = _fit(d, wagon["model"], "bold", SIZE - 2 * M,
                             60 if photo else 82, 44, max_lines=2)
    y = ky + 40
    for ln in lines:
        d.text((M, y), ln, font=font, fill=t["ink"])
        y += int(size * 1.08)
    d.text((M, y + 2), wagon.get("years", ""), font=_font("semibold", 27), fill=t["accent"])

    specs = wagon.get("specs", [])[:3]
    if specs:
        sy = SIZE - (250 if photo else 300)
        d.line([(M, sy - 26), (SIZE - M, sy - 26)], fill=t["rule"], width=2)
        col = (SIZE - 2 * M) // max(1, len(specs))
        for i, (lab, val) in enumerate(specs):
            x = M + i * col
            d.text((x, sy), lab.upper(), font=_font("regular", 19), fill=t["muted"])
            d.text((x, sy + 26), val, font=_font("bold", 36), fill=t["ink"])

    _footer(d, t, M, f"{DB_COUNT} wagons in the database - link in bio", "allthewagons.com",
            credit=wagon.get("credit"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "JPEG", quality=92)
    return out_path
