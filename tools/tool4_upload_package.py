# -*- coding: utf-8 -*-
"""Tool 4 - Upload Package Generator.

Creates YouTube titles, description, tags and a thumbnail prompt idea from a
song name. Works offline for common Telugu/English worship words.

Run standalone:  python tools/tool4_upload_package.py --title "యేసు నీ కార్యములు"
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import ensure_output_dir, sanitize_filename, banner, ask

# common worship vocabulary (Telugu + English) used to build tags
TE_WORDS = [
    "యేసు", "క్రీస్తు", "దేవుడు", "ఆరాధన", "కీర్తన", "ప్రార్థన", "స్తుతి",
    "మీరటింగ్", "బైబిలు", "పరిశుద్ధాత్మ", "దేవుని ప్రేమ", "సంగీతం", "పాట",
    "ఆశీర్వాదం", "మోక్షం", "సువార్త",
]
EN_WORDS = [
    "jesus", "christ", "god", "worship", "song", "prayer", "praise",
    "meeting", "bible", "holy spirit", "telugu christian song",
    "telugu worship", "gospel", "devotional", "blessing", "kuvi song",
    "odia christian song",
]

HASHTAGS = [
    "#యేసు #Jesus #ChristianSong #TeluguWorship #Church #Gospel #Kirtanalu",
    "#Jesus #Worship #TeluguSongs #Bible #Prayer #Praise #ChristianMusic",
]

PLACEHOLDER_URL = "https://youtu.be/PASTE_YOUR_VIDEO_LINK_HERE"
PLACEHOLDER_SECOND = "PASTE_END_SCREEN_URL_OR_REMOVE"


def build_title_variants(title):
    base = title.strip()
    return [
        base,
        f"{base} | తెలుగు క్రిస్టియన్ కీర్తన | Telugu Christian Song",
        f"{base} - Telugu Christian Worship Song",
        f"{base} ✝️ (Lyrics) Telugu Christian Song",
    ]


def build_description(title, channel, notes):
    lines = []
    lines.append(f"{title}")
    lines.append("")
    if notes:
        lines.append(notes.strip())
        lines.append("")
    lines.append(f"ఈ కీర్తనలో పాలుపంచుకున్నందుకు ధన్యవాదాలు. "
                 "మీ ప్రార్థనలు, స్ట్రీమింగ్ మాకు ఎంతో ప్రోత్సాహం.")
    lines.append("")
    lines.append("Thank you for watching! Please LIKE, SHARE and SUBSCRIBE to "
                 f"our channel {channel} for more worship songs.")
    lines.append("")
    lines.append("🙏 Share this song with your family and friends.")
    lines.append("")
    lines.append("⏱️ Chapters:")
    lines.append("00:00 - Start")
    lines.append("")
    lines.append("🔔 Subscribe: " + PLACEHOLDER_URL)
    lines.append("")
    lines.append("🎵 Song: " + title)
    lines.append("✝️ Category: Worship / Devotional")
    lines.append("🌐 Language: Telugu")
    lines.append("")
    lines.append("Life is short, eternity is long. Come to Jesus Christ. ✝️")
    return "\n".join(lines)


def build_tags(title, word_extras):
    tags = list(EN_WORDS) + list(TE_WORDS)
    tags = list(dict.fromkeys(tags))   # de-duplicate, keep order
    if word_extras:
        tags += [x.strip() for x in word_extras.split(",") if x.strip()]
    return ", ".join(tags)


def build_thumbnail_prompt(title):
    return (
        "YouTube thumbnail prompt:\n"
        f"'{title}' - Telugu Christian worship song thumbnail. "
        "Big bold Telugu title text, bright warm light, church cross and "
        "rays of light background, joyful atmosphere, HD, high contrast, "
        "clean layout, no watermark text except the title."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Upload Package Generator")
    parser.add_argument("--title", help="song title")
    parser.add_argument("--channel", default=None, help="your channel name")
    parser.add_argument("--notes", default=None, help="extra description text")
    parser.add_argument("--extra-tags", default=None, help="extra comma tags")
    parser.add_argument("--output", help="output file name (optional)")
    args = parser.parse_args(argv)

    banner("Tool 4 - Upload Package Generator")

    title = args.title or ask("Song title", default="యేసు నీ కార్యములు")
    channel = args.channel or ask("Your channel name", default="Church of Christ")
    notes = args.notes
    extra_tags = args.extra_tags
    # when invoked fully from the command line, skip interactive prompts
    if args.title and args.channel and notes is None and extra_tags is None:
        pass  # use the command-line defaults (no prompts)
    else:
        if notes is None:
            notes = ask("Extra description (Enter to skip)", default="") or None
        if extra_tags is None:
            extra_tags = ask("Extra tags, comma list (Enter to skip)", default="") or None

    outdir = ensure_output_dir()
    out_name = args.output or sanitize_filename(title + "_upload_package")
    out_path = os.path.join(outdir, out_name + ".txt")

    parts = []
    parts.append("=" * 60)
    parts.append("TITLE OPTIONS (pick one)")
    parts.append("=" * 60)
    for i, t in enumerate(build_title_variants(title), 1):
        parts.append(f"{i}. {t}")
    parts.append("")
    parts.append("=" * 60)
    parts.append("DESCRIPTION")
    parts.append("=" * 60)
    parts.append(build_description(title, channel, notes))
    parts.append("")
    parts.append("=" * 60)
    parts.append("TAGS (paste ALL in the Tags box)")
    parts.append("=" * 60)
    parts.append(build_tags(title, extra_tags))
    parts.append("")
    parts.append("=" * 60)
    parts.append("HASHTAGS")
    parts.append("=" * 60)
    for h in HASHTAGS:
        parts.append(h)
    parts.append("")
    parts.append("=" * 60)
    parts.append("THUMBNAIL IDEA (paste into ChatGPT/Firefly/Gemini)")
    parts.append("=" * 60)
    parts.append(build_thumbnail_prompt(title))
    parts.append("")
    parts.append("REMEMBER: paste your real video link over " + PLACEHOLDER_URL)

    text = "\n".join(parts)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

    print("\n[OK] Upload package written to:", out_path)
    print("\n--- Preview (first 30 lines) ---")
    for line in text.splitlines()[:30]:
        print(line)
    return 0


if __name__ == "__main__":
    main()