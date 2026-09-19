# -*- coding: utf-8 -*-
"""Tool 6 - AI Thumbnail Generator (free, no API key).

Creates a real AI-generated thumbnail image from a text prompt using the
free Pollinations.ai text-to-image API (https://pollinations.ai - no key,
no sign-up), then overlays the channel title/subtitle/logo with the same
Telugu text-shaping stack as Tool 2.

If the AI service is unreachable the tool still finishes, falling back to
an auto colour background so you always get a downloadable thumbnail.
"""
import argparse
import os
import random
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw, ImageOps

from common import (ask, banner, ensure_output_dir, sanitize_filename)
from textdraw import draw_text, line_height, measure_width, wrap_text

POLLINATIONS = "https://image.pollinations.ai/prompt/{}"
DEFAULT_MODEL = "flux"      # flux = higher quality, turbo = fast
UA = ("Mozilla/5.0 (AI-YouTube-Studio) "
      "ai-youtube-studio-thumbnail-generator")


def make_gradient(w, h):
    top = (30, 34, 96)
    bot = (139, 92, 246)
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=tuple(
            int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return im.convert("RGBA")


def fetch_ai_image(prompt, w, h, seed, model):
    """Download (w,h) AI image for the prompt. Returns PIL image or None."""
    url = (POLLINATIONS.format(urllib.parse.quote(prompt))
           + f"?width={w}&height={h}&seed={seed}&model={model}"
           + "&nologo=true&referrer=ai-youtube-studio")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if not data:
        return None
    return Image.open(__import__("io").BytesIO(data)).convert("RGBA")


def overlay_text(base, title, sub, logo):
    """Add title/sub/logo onto the image (mirrors Tool 2's look)."""
    w, h = base.size
    if title:
        shade = Image.new("RGBA", base.size, (0, 0, 0, int(255 * 0.45)))
        base.alpha_composite(shade)

    draw = ImageDraw.Draw(base, "RGBA")

    if title:
        tsize = max(40, min(int(w * 0.085), 130))
        lines = wrap_text(draw, title, tsize, int(w * 0.82))
        lh = line_height(tsize)
        block = len(lines) * lh
        y = int(h * 0.40 - block / 2)
        for ln in lines:
            tw = measure_width(draw, ln, tsize)
            x = int((w - tw) / 2)
            draw_text(draw, (x, y), ln, tsize, bold=True,
                      fill=(255, 255, 255, 255), stroke=(0, 0, 0, 255), sw=4)
            y += lh

    if sub:
        ssize = max(22, min(int(w * 0.045), 64))
        sw = measure_width(draw, sub, ssize)
        draw_text(draw, (int((w - sw) / 2), y + int(lh * 0.35)),
                  sub, ssize, bold=False,
                  fill=(230, 230, 255, 255), stroke=(0, 0, 0, 255), sw=3)

    if logo and os.path.isfile(logo):
        try:
            lg = Image.open(logo).convert("RGBA")
            lg.thumbnail((w, int(h * 0.14)))
            base.alpha_composite(lg,
                                 (w - lg.width - 20, h - lg.height - 20))
        except Exception:
            pass
    return base


def main(argv=None):
    parser = argparse.ArgumentParser(description="AI Thumbnail Generator")
    parser.add_argument("--prompt", help="what to draw, e.g. 'worship guitar, "
                                         "golden sunset, cinematic'")
    parser.add_argument("--title", help="overlay title text (Telugu/English)")
    parser.add_argument("--sub", help="small subtitle under the title")
    parser.add_argument("--logo", help="channel logo image (optional)")
    parser.add_argument("--size", default="1280x720",
                        help="WxH (default 1280x720)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help="flux or turbo (default flux)")
    parser.add_argument("--seed", type=int, default=None,
                        help="fixed seed for reproducible images")
    parser.add_argument("--output", help="output file name (optional)")
    args = parser.parse_args(argv)

    banner("Tool 6 - AI Thumbnail Generator (free, no key)")

    prompt = args.prompt or ask(
        "Describe the image (English works best), e.g. "
        "'worship guitar golden sunset cinematic'") or "worship music"
    title = args.title
    if title is None:
        title = ask("Overlay title text (Enter to skip)", default="").strip() or None
    sub = args.sub or None
    logo = args.logo or None

    try:
        w, h = (int(x) for x in args.size.lower().split("x"))
    except ValueError:
        w, h = 1280, 720
    seed = args.seed if args.seed is not None else random.randint(0, 2 ** 31)

    print("  Generating with Pollinations.ai "
          f"({args.model}, {w}x{h}, seed {seed}) ...")
    base = None
    try:
        base = fetch_ai_image(prompt, w, h, seed, args.model)
        if base is not None:
            print("  [OK] AI image downloaded")
    except Exception as e:
        print(f"  [WARN] AI service unreachable ({type(e).__name__}) - "
              "using auto colour background instead")

    if base is None:
        base = make_gradient(w, h)
    base = ImageOps.fit(base, (w, h), Image.LANCZOS)

    base = overlay_text(base, title, sub, logo)

    outdir = ensure_output_dir()
    out_name = args.output or sanitize_filename((title or prompt) + "_ai_thumb")
    png = os.path.join(outdir, out_name + ".png")
    jpg = os.path.join(outdir, out_name + ".jpg")
    base.convert("RGB").save(png)
    base.convert("RGB").save(jpg, quality=92)
    print(f"[OK] Thumbnails saved to:\n  {png}\n  {jpg}")


if __name__ == "__main__":
    main()