# -*- coding: utf-8 -*-
"""Tool 2 - AI Thumbnail Studio.

Creates a 1280x720 YouTube thumbnail from a title + optional subtitle,
background image, and channel logo. Telugu/emoji friendly.

Run standalone: python tools/tool2_thumbnail_studio.py --title "యేసు నా రాజా"
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (ensure_output_dir, sanitize_filename, ask, banner)
from textdraw import (measure_width, wrap_text, draw_text,
                      rounded_rect, text_bbox)

TW, TH = 1280, 720


def make_gradient(c1=(16, 24, 64), c2=(120, 20, 90)):
    from PIL import Image
    grad = Image.new("RGB", (1, TH))
    for y in range(TH):
        f = y / max(1, TH - 1)
        grad.putpixel((0, y), tuple(int(c1[i] + (c2[i] - c1[i]) * f)
                                    for i in range(3)))
    return grad.resize((TW, TH))


def cover_crop(img, tw=TW, th=TH):
    w, h = img.size
    scale = max(tw / w, th / h)
    nw, nh = int(w * scale + 0.5), int(h * scale + 0.5)
    img = img.resize((nw, nh), 1)
    x0 = max(0, (nw - tw) // 2)
    y0 = max(0, (nh - th) // 2)
    return img.crop((x0, y0, x0 + tw, y0 + th))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Thumbnail Studio")
    parser.add_argument("--title", help="main title text (Telugu/English)")
    parser.add_argument("--sub", help="small subtitle text (optional)")
    parser.add_argument("--background", help="background image (optional)")
    parser.add_argument("--logo", help="channel logo image (optional)")
    parser.add_argument("--output", help="output file name (optional)")
    args = parser.parse_args(argv)

    banner("Tool 2 - AI Thumbnail Studio")

    title = args.title or ask("Title text (Telugu/English)", default="యేసు")
    sub = args.sub
    if sub is None:
        sub = ask("Small subtitle text (Enter to skip)", default="")
        sub = sub or None
    bg_path = args.background
    if bg_path is None:
        bg_path = ask("Background image (Enter for auto colour)", default="")
    bg_path = bg_path or None
    logo = args.logo
    if logo is None:
        logo = ask("Channel logo (Enter to skip)", default="")
    logo = logo or None

    from PIL import Image, ImageDraw

    # by default add a subtle dark shade over background for text contrast
    shade = 0.45 if bg_path else 0.0
    outdir = ensure_output_dir()
    out_name = args.output or sanitize_filename(title + "_thumb")
    out_png = os.path.join(outdir, out_name + ".png")
    out_jpg = os.path.join(outdir, out_name + ".jpg")

    print("\nDrawing thumbnail ...")
    if bg_path and os.path.isfile(bg_path):
        try:
            base = Image.open(bg_path).convert("RGB")
            base = cover_crop(base)
        except Exception:
            base = make_gradient()
    else:
        base = make_gradient()

    base = base.convert("RGBA")
    if shade > 0:
        ov = Image.new("RGBA", base.size, (0, 0, 0, int(255 * shade)))
        base = Image.alpha_composite(base, ov)

    draw = ImageDraw.Draw(base)

    # --- main title: stack up to 2 lines, auto-fit font size
    title_font_size = fit_title_size(draw, title, 60, 150)
    pieces = split_title(title, int(TW * 0.92), title_font_size)
    while len(pieces) > 2:
        title_font_size = int(title_font_size * 0.85)
        pieces = split_title(title, int(TW * 0.92), title_font_size)
    block_h = len(pieces) * int(title_font_size * 1.3)
    y = int(TH * 0.07)
    for piece in pieces:
        wpx = measure_width(draw, piece, title_font_size, bold=True)
        x = (TW - int(wpx)) // 2
        # white slab behind text for guaranteed contrast
        bb = text_bbox(draw, piece, title_font_size, bold=True)
        hpx = (bb[3] - bb[1]) or title_font_size
        pad = 16
        rounded_rect(base, (x - pad, y - 8, x + int(wpx) + pad,
                            y + hpx + 10),
                     radius=18, fill=(255, 255, 255, 235))
        draw_text(draw, (x, y), piece, title_font_size, bold=True,
                  fill=(10, 10, 20, 255))
        y += int(title_font_size * 1.28)

    # --- subtitle near the bottom
    if sub:
        sub_size = 56
        lines = wrap_text(draw, sub, sub_size, int(TW * 0.9), bold=True)
        yy = TH - int(TH * 0.13)
        for ln in lines:
            wpx = measure_width(draw, ln, sub_size, bold=True)
            x = (TW - int(wpx)) // 2
            draw_text(draw, (x, yy), ln, sub_size, bold=True,
                      fill=(255, 220, 0, 255), stroke=(0, 0, 0, 255), sw=3)
            yy += int(sub_size * 1.35)

    # --- logo bottom-right
    if logo and os.path.isfile(logo):
        try:
            lg = Image.open(logo).convert("RGBA")
            lw, lh = lg.size
            scale = int(TH * 0.14) / max(lw, lh)
            lg = lg.resize((max(1, int(lw * scale)), max(1, int(lh * scale))), 1)
            pad = 16
            base.alpha_composite(lg, (TW - lg.size[0] - pad, TH - lg.size[1] - pad))
        except Exception:
            pass

    base.convert("RGB").save(out_png)
    base.convert("RGB").save(out_jpg, quality=92)
    print("[OK] Thumbnails saved:")
    print("     ", out_png)
    print("     ", out_jpg)
    return 0


def fit_title_size(draw, title, min_size, max_size):
    """Biggest font size where the whole title fits on 2 lines."""
    size = max_size
    while size >= min_size:
        pieces = split_title(title, int(TW * 0.92), size)
        if len(pieces) <= 2:
            widths = [measure_width(draw, p, size, bold=True) for p in pieces]
            if all(w <= TW * 0.94 for w in widths):
                return size
        size -= 10
    return min_size


def split_title(title, max_width, font_size):
    """Split a title into up to 3 poster lines at word boundaries."""
    words = title.split(" ")
    if len(words) <= 1:
        return [title]
    total = len(title)
    if total <= 12:
        return [title]
    # split as close to the middle as possible
    target = total // 2
    best = None
    acc = 0
    for i, w in enumerate(words[:-1]):
        acc += len(w) + 1
        if best is None or abs(acc - target) < abs(best[0] - target):
            best = (acc, i + 1)
    _, idx = best
    line1 = " ".join(words[:idx])
    line2 = " ".join(words[idx:])
    # fall back to a char split if a single word is enormous
    if max(len(line1), len(line2)) > 22:
        half = len(title) // 2
        line1 = title[:half]
        line2 = title[half:]
    return [line1, line2]


if __name__ == "__main__":
    main()