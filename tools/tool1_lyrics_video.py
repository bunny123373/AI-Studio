# -*- coding: utf-8 -*-
"""Tool 1 - Auto Lyrics Video Maker.

Takes  audio + lyrics (.srt/.lrc/.txt) + optional background (video/image)
and produces a finished Telugu/Kuvi lyric video.

Run standalone:   python tools/tool1_lyrics_video.py --audio song.mp3 --lyrics song.srt
or pick tool 1 in studio.py.
"""
import argparse
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (ensure_output_dir, require_ffmpeg, sanitize_filename,
                    ask, yes_no, banner)
from textdraw import get_fonts, measure_width, wrap_text, draw_text, rounded_rect


# ---------------------------------------------------------------- lyrics parse

def parse_srt(path):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        raw = f.read()
    blocks = re.split(r"\n\s*\n", raw.strip())
    subs = []
    for b in blocks:
        lines = [l.strip() for l in b.splitlines() if l.strip()]
        if not lines:
            continue
        if lines[0].isdigit():
            lines = lines[1:]
        if not lines:
            continue
        m = re.match(
            r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
            r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})", lines[0])
        if not m:
            continue
        g = m.groups()
        t1 = int(g[0]) * 3600000 + int(g[1]) * 60000 + int(g[2]) * 1000 + int(g[3])
        t2 = int(g[4]) * 3600000 + int(g[5]) * 60000 + int(g[6]) * 1000 + int(g[7])
        text = "\n".join(lines[1:])
        if text:
            subs.append((t1, t2, text))
    subs.sort()
    return subs


def parse_lrc(path):
    out = []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            m = list(re.finditer(r"\[(\d{1,2}):(\d{2})[.:](\d{1,3})\]",
                                 line.strip()))
            if not m:
                continue
            text = line.strip()[m[-1].end():].strip()
            for mm in m:
                t = int(mm.group(1)) * 60000 + int(mm.group(2)) * 1000
                frac = mm.group(3)
                t += int(frac.ljust(3, "0")[:3])
                out.append((t, text))
    out.sort()
    # fill end times
    segs = []
    for i, (t, text) in enumerate(out):
        end = out[i + 1][0] - 1 if i + 1 < len(out) else t + 3000
        segs.append((t, end, text))
    return segs


def parse_txt(path, duration_ms):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        lines = [l.strip() for l in f if l.strip()]
    if not lines:
        return []
    step = duration_ms / len(lines)
    return [(int(i * step), int((i + 1) * step), ln)
            for i, ln in enumerate(lines)]


def load_segments(lyrics_path, duration_ms):
    ext = os.path.splitext(lyrics_path)[1].lower()
    if ext == ".srt":
        return parse_srt(lyrics_path)
    if ext == ".lrc":
        return parse_lrc(lyrics_path)
    return parse_txt(lyrics_path, duration_ms)


# ---------------------------------------------------------------- background

def cover_crop(img, tw, th):
    """Resize+crop img so it exactly covers (tw, th)."""
    w, h = img.size
    scale = max(tw / w, th / h)
    nw, nh = int(w * scale + 0.5), int(h * scale + 0.5)
    img = img.resize((nw, nh), 1)
    x0 = max(0, (nw - tw) // 2)
    y0 = max(0, (nh - th) // 2)
    return img.crop((x0, y0, x0 + tw, y0 + th))


def make_gradient(tw, th, c1=(16, 16, 48), c2=(55, 16, 80), pulse=False, t=0.0):
    from PIL import Image
    if pulse:
        a = 0.5 + 0.5 * math.sin(2 * math.pi * t / 8.0)
        c1 = tuple(int(v * (1 - 0.25 * a)) for v in c1)
        c2 = tuple(int(v + (255 - v) * 0.08 * a) for v in c2)
    grad = Image.new("RGB", (1, th))
    for y in range(th):
        f = y / max(1, th - 1)
        grad.putpixel((0, y), tuple(int(c1[i] + (c2[i] - c1[i]) * f)
                                    for i in range(3)))
    return grad.resize((tw, th))


class Background:
    """Frame provider: (t) -> PIL RGB image of size (tw, th)."""

    def __init__(self, source, tw, th):
        self.source = source
        self.tw, self.th = tw, th
        self.video = None
        self.image = None
        if source and os.path.splitext(source)[1].lower() in (
                ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"):
            from moviepy import VideoFileClip
            self.video = VideoFileClip(source, audio=False)
        elif source:
            from PIL import Image
            self.image = Image.open(source).convert("RGB")

    def frame(self, t):
        if self.video is not None:
            fr = self.video.get_frame(t % max(0.01, self.video.duration))
            from PIL import Image
            return cover_crop(Image.fromarray(fr), self.tw, self.th)
        if self.image is not None:
            # gentle Ken Burns zoom
            dur_div = 60.0
            z = 1.0 + 0.10 * math.sin(2 * math.pi * t / dur_div)
            img = cover_crop(self.image, self.tw, self.th)
            if abs(z - 1.0) > 0.001:
                nw, nh = int(self.tw * z), int(self.th * z)
                img = img.resize((nw, nh), 1)
                x0 = max(0, (nw - self.tw) // 2)
                y0 = max(0, (nh - self.th) // 2)
                img = img.crop((x0, y0, x0 + self.tw, y0 + self.th))
            return img
        return make_gradient(self.tw, self.th, pulse=True, t=t)

    def close(self):
        if self.video is not None:
            try:
                self.video.close()
            except Exception:
                pass


# ---------------------------------------------------------------- rendering

def active_segment(segs, ms):
    for s in segs:
        if s[0] <= ms < s[1]:
            return s
    return None


# the real frame renderer class -------------------------------------------------

class Renderer:
    def __init__(self, segs, bg, tw, th, logo=None, sub_size=None, logo_max=None):
        self.segs = segs
        self.bg = bg
        self.tw, self.th = tw, th
        self.logo = logo
        self.sub_size = sub_size or max(28, int(th * 0.058))
        self.logo_max = logo_max or int(th * 0.10)
        self._logo_img = None
        if logo:
            from PIL import Image
            try:
                self._logo_img = Image.open(logo).convert("RGBA")
                w, h = self._logo_img.size
                scale = self.logo_max / max(w, h)
                self._logo_img = self._logo_img.resize(
                    (max(1, int(w * scale)), max(1, int(h * scale))), 1)
            except Exception:
                self._logo_img = None

    def make_frame(self, t):
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont
        ms = int(t * 1000)
        im = self.bg.frame(t).convert("RGBA")
        draw = ImageDraw.Draw(im)
        tw, th = self.tw, self.th

        # logo watermark bottom-right
        if self._logo_img is not None:
            lw, lh = self._logo_img.size
            pad = max(10, int(th * 0.02))
            logo = self._logo_img.copy()
            logo.putalpha(int(200))
            im.alpha_composite(logo, (tw - lw - pad, th - lh - pad))

        # active subtitle
        seg = active_segment(self.segs, ms)
        if seg:
            s0, s1, text = seg
            fade = 200
            if ms - s0 < 180:
                fade = int(200 * (ms - s0) / 180)
            if s1 - ms < 180:
                fade = int(200 * (s1 - ms) / 180)
            fade = max(20, min(255, fade))
            lines = text.split("\n")
            wrapped = []
            for ln in lines:
                wrapped += wrap_text(draw, ln, self.sub_size,
                                     int(tw * 0.92), bold=True)
            wrapped = wrapped[:3]
            box_h = len(wrapped) * int(self.sub_size * 1.45)
            y0 = th - box_h - int(th * 0.10)
            x0 = int(tw * 0.04)
            x1 = tw - x0
            rounded_rect(im, (x0, y0 - 12, x1, y0 + box_h + 8),
                         radius=16,
                         fill=(0, 0, 0, int(150 * fade / 255)))
            y = y0
            for ln in wrapped:
                wpx = measure_width(draw, ln, self.sub_size, bold=True)
                x = (tw - int(wpx)) // 2
                draw_text(draw, (x, y), ln, self.sub_size, bold=True,
                          fill=(255, 255, 255, fade),
                          stroke=(0, 0, 0, fade), sw=2)
                y += int(self.sub_size * 1.45)

        return np.array(im.convert("RGB"))


# ---------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(description="Lyrics Video Maker")
    parser.add_argument("--audio", help="song file (mp3/wav/m4a)")
    parser.add_argument("--lyrics", help=".srt / .lrc / .txt lyrics file")
    parser.add_argument("--background", help="background video or image (optional)")
    parser.add_argument("--logo", help="channel logo image (optional)")
    parser.add_argument("--output", help="output file name (optional)")
    parser.add_argument("--res", default="1280x720", help="WxH, default 1280x720")
    parser.add_argument("--fps", type=int, default=30)
    args = parser.parse_args(argv)

    banner("Tool 1 - Auto Lyrics Video Maker")

    require_ffmpeg()
    from moviepy import AudioFileClip, VideoClip

    audio = args.audio or ask("Song file (mp3/wav/m4a)")
    if not audio or not os.path.isfile(audio):
        print("[ERROR] Audio file not found:", audio)
        sys.exit(1)
    lyrics = args.lyrics or ask("Lyrics file (.srt / .lrc / .txt)")
    if not lyrics or not os.path.isfile(lyrics):
        print("[ERROR] Lyrics file not found:", lyrics)
        sys.exit(1)

    background = args.background
    if background is None:
        background = ask("Background video or image (Enter for auto colour)",
                         default="")
        background = background or None
    logo = args.logo
    if logo is None:
        logo = ask("Channel logo image (Enter to skip)", default="")
        logo = logo or None

    try:
        tw, th = (int(x) for x in args.res.lower().split("x"))
    except Exception:
        tw, th = 1280, 720

    outdir = ensure_output_dir()
    out_name = args.output or sanitize_filename(
        os.path.splitext(os.path.basename(audio))[0] + "_lyrics")
    out_path = os.path.join(outdir, out_name + ".mp4")

    print("\nAnalyzing audio ...")
    audio_clip = AudioFileClip(audio)
    dur_ms = int(audio_clip.duration * 1000)
    segs = load_segments(lyrics, dur_ms)
    if not segs:
        print("[ERROR] No lyrics were found in that file.")
        sys.exit(1)
    print(f"  audio length : {audio_clip.duration:.1f}s")
    print(f"  lyric lines  : {len(segs)}")

    print("\nPreparing background ...")
    bg = Background(background, tw, th)
    renderer = Renderer(segs, bg, tw, th, logo=logo)

    print("Rendering video ... (please wait, this takes a few minutes)")
    clip = VideoClip(frame_function=renderer.make_frame,
                     duration=audio_clip.duration).with_audio(audio_clip)
    try:
        clip.write_videofile(
            out_path, fps=args.fps, codec="libx264", audio_codec="aac",
            preset="medium", logger=None)
    finally:
        bg.close()
        try:
            audio_clip.close()
        except Exception:
            pass

    print("\n[OK] Video saved to:", out_path)
    return 0


if __name__ == "__main__":
    main()