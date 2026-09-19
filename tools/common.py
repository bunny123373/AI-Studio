# -*- coding: utf-8 -*-
"""Shared helpers for all 5 AI YouTube Studio tools."""
import os
import sys
import shutil
import unicodedata

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# AI_STUDIO_OUTPUT lets a deployed web service point tools at a persistent
# disk mount (Render/Railway/etc.). Falls back to <project>/output.
OUTPUT_DIR = os.environ.get("AI_STUDIO_OUTPUT") or os.path.join(BASE_DIR, "output")
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")
FONTS_DIR = os.path.join(BASE_DIR, "fonts")


def _fix_console():
    """Windows console is cp1252 by default -> force UTF-8 so Telugu prints."""
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_fix_console()

# Telugu-capable fonts on Windows (ordered by preference)
FONT_BOLD_CANDIDATES = [
    "C:/Windows/Fonts/NirmalaB.ttf",
    "C:/Windows/Fonts/Vanib.ttf",
    "C:/Windows/Fonts/gautamib.ttf",
]
FONT_REGULAR_CANDIDATES = [
    "C:/Windows/Fonts/Nirmala.ttf",
    "C:/Windows/Fonts/Vani.ttf",
    "C:/Windows/Fonts/gautami.ttf",
]
EMOJI_FONT_CANDIDATES = [
    "C:/Windows/Fonts/seguiemj.ttf",  # Segoe UI Emoji
    "C:/Windows/Fonts/seguiemj.ttc",
]


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return OUTPUT_DIR


def find_ffmpeg():
    """Locate an ffmpeg binary (user env, system, or imageio-ffmpeg bundle)."""
    env = os.environ.get("FFMPEG_PATH")
    if env and os.path.isfile(env):
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass
    return None


def require_ffmpeg():
    path = find_ffmpeg()
    if not path:
        print("[ERROR] ffmpeg was not found. Run setup.bat once to install it.")
        sys.exit(1)
    return path


def _scan_fonts(filenames):
    """Search common Linux font dirs for any of the given filenames."""
    roots = ["/usr/share/fonts", os.path.expanduser("~/.fonts"),
             os.path.expanduser("~/.local/share/fonts")]
    targets = {f.lower() for f in filenames}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if f.lower() in targets:
                    return os.path.join(dirpath, f)
    return None


def find_font(bold=True):
    """Return a path to a Telugu-capable .ttf font, or None."""
    for cand in (FONT_BOLD_CANDIDATES if bold else FONT_REGULAR_CANDIDATES):
        if os.path.isfile(cand):
            return cand
    # Linux (deployed) fallback: Noto Sans Telugu from fonts-noto-core/extra
    names = (["NotoSansTelugu-Bold.ttf", "NotoSansTelugu-Bold.ttc",
              "NotoSansTelugu-SemiBold.ttf"] if bold else
             ["NotoSansTelugu-Regular.ttf", "NotoSansTelugu-Medium.ttf",
              "NotoSansTelugu.ttf"])
    return _scan_fonts(names)


def find_emoji_font():
    for cand in EMOJI_FONT_CANDIDATES:
        if os.path.isfile(cand):
            return cand
    return _scan_fonts(["NotoColorEmoji.ttf", "NotoColorEmoji-Regular.ttf"])


def is_emoji_char(ch):
    cp = ord(ch)
    return (
        0x1F000 <= cp <= 0x1FAFF
        or 0x2600 <= cp <= 0x27BF
        or 0x2B00 <= cp <= 0x2BFF
        or 0x2190 <= cp <= 0x21FF
        or cp in (0xFE0F, 0x200D, 0x20E3)
    )


def split_mixed(text):
    """Split a string into (is_emoji, chunk) runs so we can use two fonts."""
    runs = []
    for ch in text:
        emoji = is_emoji_char(ch)
        if ch == " ":  # spaces belong to the previous run
            runs.append((emoji if runs else False, ch))
        elif runs and runs[-1][0] == emoji:
            runs[-1] = (emoji, runs[-1][1] + ch)
        else:
            runs.append((emoji, ch))
    return runs


def sanitize_filename(name, fallback="output"):
    keep = []
    for ch in name:
        if ch.isalnum() or ch in "._- ":
            keep.append(ch)
        elif unicodedata.category(ch).startswith("M"):
            keep.append(ch)  # combining marks (ే ు ా ...) belong to letters
        else:
            keep.append("_")
    out = "".join(keep).strip().replace(" ", "_")
    return out[:60] or fallback


def ask(question, default=None):
    suffix = "" if default is None else f"  [{default}]"
    try:
        answer = input(question + suffix + " : ").strip()
    except EOFError:
        answer = ""
    if not answer and default is not None:
        return default
    return answer


def yes_no(question, default=True):
    val = ask(question, "y" if default else "n").lower()
    return val.startswith("y")


def banner(title):
    print("")
    print("=" * 60)
    print("  " + title)
    print("=" * 60)