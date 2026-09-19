# -*- coding: utf-8 -*-
"""Telugu text rendering with proper OpenType shaping (HarfBuzz).

Pillow's basic layouter cannot shape Indic scripts (conjuncts like క్రీస్తు,
stroke/raqm issues), so we shape text with uharfbuzz and render the glyphs
with freetype-py. Falls back to plain Pillow if those libs are missing.
Emoji runs are drawn with the Segoe UI Emoji font via Pillow.
"""
import os

from PIL import Image, ImageDraw, ImageFont, features

from common import find_font, find_emoji_font, split_mixed

HAS_RAQM = features.check("raqm")
try:
    import uharfbuzz as _hb
    import freetype as _ft
    HAS_SHAPING = True
except Exception:
    _hb = _ft = None
    HAS_SHAPING = False

_pil_fonts = {}
_shaper_cache = {}


def _ttf(path, size):
    if path and os.path.isfile(path):
        return ImageFont.truetype(path, size)
    return None


def get_fonts(size, bold=True):
    """Return (pil_telugu_font, pil_emoji_font) for the given size."""
    key = (size, bold)
    if key not in _pil_fonts:
        _pil_fonts[key] = (
            _ttf(find_font(bold=bold), size),
            _ttf(find_emoji_font(), size),
        )
    return _pil_fonts[key]


def has_shaping():
    return HAS_SHAPING


# ------------------------------------------------------------- HarfBuzz core

class _Shaper:
    def __init__(self, path, size):
        self.path, self.size = path, size
        self.hb_font = _hb.Font(_hb.Face(_hb.Blob.from_file_path(path)))
        self.ft_face = _ft.Face(path)
        self.ft_face.set_pixel_sizes(0, size)
        # freetype-py metrics are in 26.6 fixed point -> divide by 64
        self.ascent = max(1, int(getattr(self.ft_face, "ascender", size * 64) / 64))
        self.descent = abs(int(getattr(self.ft_face, "descender", 0) / 64))
        self.height = self.ascent + self.descent
        upem = self.hb_font.face.upem

        def _emit(msg):
            pass
        self.scale = size / upem

    def shape(self, text):
        buf = _hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        _hb.shape(self.hb_font, buf)
        return buf.glyph_infos, buf.glyph_positions

    def advance(self, text):
        infos, pos = self.shape(text)
        return sum(p.x_advance for p in pos) * self.scale

    def _glyph(self, gid):
        try:
            self.ft_face.load_glyph(gid,
                                    _ft.FT_LOAD_RENDER | _ft.FT_LOAD_NO_HINTING)
            return self.ft_face.glyph
        except Exception:
            return None


def _get_shaper(path, size):
    key = (path, size)
    if key not in _shaper_cache:
        try:
            _shaper_cache[key] = _Shaper(path, size)
        except Exception:
            _shaper_cache[key] = None
    return _shaper_cache[key]


def shaped_metrics(text, size, bold=True):
    """(width, ascent, height) for a pure Telugu string, or None if not shaped."""
    path = find_font(bold=bold)
    if not HAS_SHAPING or not path:
        return None
    sh = _get_shaper(path, size)
    if sh is None:
        return None
    return sh.advance(text), sh.ascent, sh.height


def _render_shaped_into(layer, draw, text, size, bold, fill, stroke, sw, x0, baseline):
    """Draw one shaped run into `layer` (RGBA image) using uharfbuzz glyphs."""
    path = find_font(bold=bold)
    if not path:
        return False
    sh = _get_shaper(path, size)
    if sh is None:
        return False
    infos, pos = sh.shape(text)
    s = sh.scale
    pen = float(x0)
    fill_px = fill[:3] + (255,)
    stroke_px = (stroke[:3] + (255,)) if stroke else None

    def blit(pen_x, pen_y, color):
        for gidp in zip(infos, pos):
            gid, p = gidp[0].codepoint, gidp[1]
            glyph = sh._glyph(gid)
            if glyph is None:
                pen_x += p.x_advance * s
                continue
            bmp = glyph.bitmap
            if bmp.width and bmp.rows and bmp.buffer:
                alpha = Image.frombuffer(
                    "L", (bmp.width, bmp.rows), bytes(bmp.buffer),
                    "raw", "L", bmp.pitch, 1)
                color_img = Image.new("RGBA", (bmp.width, bmp.rows), color)
                color_img.putalpha(alpha)
                bx = int(pen_x + p.x_offset * s + glyph.bitmap_left)
                by = int(pen_y + p.y_offset * s - glyph.bitmap_top)
                layer.alpha_composite(color_img, (bx, by))
            pen_x += p.x_advance * s

    # stroke pass (text drawn sw px in each direction)
    if stroke_px and sw > 0:
        offs = [(dx, dy) for dx in (-sw, 0, sw) for dy in (-sw, 0, sw)]
        for dx, dy in offs:
            blit(pen + dx, baseline + dy, stroke_px)
    blit(pen, baseline, fill_px)
    return True


# ------------------------------------------------------------- public API

def measure_width(draw, text, size, bold=True):
    """Pixel width of (possibly mixed) text, shaped when possible."""
    total = 0.0
    for is_emoji, chunk in split_mixed(text):
        if is_emoji:
            tel, emo = get_fonts(size, bold)
            f = emo or tel
            if f is None:
                total += len(chunk) * size * 0.6
            else:
                total += draw.textlength(chunk, font=f,
                                         **({"direction": "ltr"}
                                            if HAS_RAQM else {}))
        else:
            m = shaped_metrics(chunk, size, bold)
            if m is not None:
                total += m[0]
            else:
                tel, emo = get_fonts(size, bold)
                f = tel
                if f is None:
                    total += len(chunk) * size * 0.6
                else:
                    total += draw.textlength(chunk, font=f)
    return total


def line_height(size, bold=True):
    """Approximate rendered line height in px."""
    m = shaped_metrics("అ", size, bold)
    if m is not None:
        return m[2]
    return int(size * 1.35)


def wrap_text(draw, text, size, max_width, bold=True):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        candidate = w if not cur else cur + " " + w
        if measure_width(draw, candidate, size, bold) <= max_width or not cur:
            cur = candidate
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_text(draw, xy, text, size, bold=True,
              fill=(255, 255, 255, 255), stroke=(0, 0, 0, 255), sw=0):
    """Draw mixed Telugu+emoji text at xy with optional outline."""
    x, y = xy
    im = getattr(draw, "_image", None)
    if im is None or im.mode not in ("RGBA", "RGB", "L"):
        # no safe target image; fall back to naive drawer
        _naive_draw(draw, xy, text, size, bold, fill, stroke, sw)
        return

    width = int(measure_width(draw, text, size, bold)) + 1
    height = line_height(size, bold)
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)

    # baseline of the line within the layer
    m = shaped_metrics("అ", size, bold)
    baseline_r = m[1] if m else int(size * 0.8)

    pen = 0.0
    for is_emoji, chunk in split_mixed(text):
        tel, emo = get_fonts(size, bold)
        f = emo if (is_emoji and emo) else None
        if f is None:
            done = _render_shaped_into(layer, ld, chunk, size, bold,
                                       fill, stroke, sw, int(pen), baseline_r)
            if not done:  # shaping unavailable -> naive fallback
                _naive_draw(ld, (int(pen), 0), chunk, size, bold,
                            fill, stroke, sw)
            pen += max(1.0, measure_width(ld, chunk, size, bold))
        else:
            _naive_draw(ld, (int(pen), 0), chunk, size, bold,
                        fill, stroke, sw, font_override=f)
            pen += max(1.0, measure_width(ld, chunk, size, bold))

    if im.mode == "RGBA":
        im.alpha_composite(layer, (x, y))
    else:
        rgba = im.convert("RGBA")
        rgba.alpha_composite(layer, (x, y))
        im.paste(rgba.convert(im.mode), (0, 0))


def _naive_draw(draw, xy, text, size, bold, fill, stroke, sw, font_override=None):
    """Fallback Pillow drawer with manual outline (no raqm needed)."""
    x, y = xy
    if font_override is not None:
        tel, emo = None, font_override
    else:
        tel, emo = get_fonts(size, bold)
    f = emo or tel
    if f is None:
        return
    conf = {"direction": "ltr", "features": ["kern"]} if HAS_RAQM else {}
    for is_emoji, chunk in split_mixed(text):
        ff = f
        if stroke and sw > 0:
            offs = [(dx, dy) for dx in (-sw, 0, sw) for dy in (-sw, 0, sw)]
            for dx, dy in offs:
                draw.text((x + dx, y + dy), chunk, font=ff, fill=stroke, **conf)
        draw.text((x, y), chunk, font=ff, fill=fill, **conf)
        x += draw.textlength(chunk, font=ff, **conf)


def text_bbox(draw, text, size, bold=True):
    """Approximate bbox (x0, y0, x1, y1) of the first line."""
    w = measure_width(draw, text, size, bold)
    h = line_height(size, bold)
    return (0, 0, int(w) + 1, h)


def rounded_rect(im, box, radius, fill):
    d = ImageDraw.Draw(im, "RGBA")
    x0, y0, x1, y1 = box
    d.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)