# -*- coding: utf-8 -*-
"""Tool 3 - Auto Subtitle & Translation.

Transcribes an audio/video file to .srt (Whisper AI) and can translate the
lyrics into several languages at once.

Run standalone:
  python tools/tool3_subtitle_translate.py --input song.mp3 --targets te en hi
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import ensure_output_dir, sanitize_filename, banner, ask

LANG_NAMES = {
    "te": "Telugu", "en": "English", "hi": "Hindi", "or": "Odia/Oriya",
    "kn": "Kannada", "ta": "Tamil", "ml": "Malayalam", "mr": "Marathi",
    "bn": "Bengali", "gu": "Gujarati", "ur": "Urdu",
}
DEFAULT_MODEL = "small"   # tiny / base / small / medium


def fmt_ts(ms):
    ms = max(0, int(ms))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, (t0, t1, text) in enumerate(segments, 1):
            f.write(f"{i}\n{fmt_ts(t0)} --> {fmt_ts(t1)}\n{text}\n\n")


def merge_segments(segs, gap_ms=450, max_chars=42):
    """Join consecutive whisper segments into subtitle-sized blocks."""
    merged = []
    for t0, t1, text in segs:
        if not merged:
            merged.append([t0, t1, text])
            continue
        prev = merged[-1]
        if (t0 - prev[1] < gap_ms and len(prev[2]) + len(text) <= max_chars):
            prev[1] = t1
            prev[2] = prev[2] + " " + text.strip() if prev[2] else text
        else:
            merged.append([t0, t1, text])
    return [(t0, t1, t.strip()) for t0, t1, t in merged if t.strip()]


def transcribe(path, model_size, language):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print()
        print("[ERROR] faster-whisper is not installed.")
        print("        Run  setup.bat  again, or install manually with:")
        print("        python -m pip install faster-whisper")
        print("        (internet connection needed)")
        sys.exit(1)
    print(f"\nLoading Whisper model '{model_size}' (first run downloads it)...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    print("Transcribing (this takes a while for long audio)...")
    segments, info = model.transcribe(
        path, language=language, vad_filter=True, beam_size=5)
    out = []
    for seg in segments:
        out.append((seg.start * 1000, seg.end * 1000, seg.text.strip()))
    detected = getattr(info, "language", "?")
    print(f"[OK] Detected language: {detected}  ({len(out)} raw segments)")
    return out


def translate_text(text, target):
    try:
        from deep_translator import GoogleTranslator
        tr = GoogleTranslator(source="auto", target=target)
        res = tr.translate(text)
        return res if res else text
    except Exception as e:
        print(f"[WARN] Translation failed for a line ({e}) - keeping original.")
        return text


BATCH = 12   # lines per bulk request (fewer calls, less rate limiting)


def translate_batch_text(lines, target):
    """Translate many lines in one batch request. Falls back to original text."""
    try:
        from deep_translator import GoogleTranslator
        tr = GoogleTranslator(source="auto", target=target)
        res = tr.translate_batch(list(lines))
    except Exception as e:
        print(f"[WARN] Batch translation failed ({e}) - keeping original.")
        res = []
    out = []
    for orig, trans in zip(lines, res):
        out.append(trans if (trans and trans.strip()) else orig)
    return out


def translate_srt(segs, target):
    """Translate subtitle texts in batches, keeping timings."""
    out = []
    total = len(segs)
    print(f"  translating to {LANG_NAMES.get(target, target)} ({total} lines)...")
    for start in range(0, total, BATCH):
        chunk = segs[start:start + BATCH]
        translated = translate_batch_text([t for _, _, t in chunk], target)
        for (t0, t1, _), nt in zip(chunk, translated):
            out.append((t0, t1, nt))
        done = min(start + BATCH, total)
        print(f"    {done}/{total}")
        if done < total:
            time.sleep(1.5)   # avoid hitting rate limits between batches
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Subtitle & Translation")
    parser.add_argument("--input", help="audio or video file")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"tiny/base/small/medium (default {DEFAULT_MODEL})")
    parser.add_argument("--lang", default=None,
                        help="source language code, e.g. te (default: auto)")
    parser.add_argument("--targets", default="", nargs="*",
                        help="translate to codes, e.g. te en hi or")
    parser.add_argument("--output", help="output base name (optional)")
    args = parser.parse_args(argv)

    banner("Tool 3 - Auto Subtitle & Translation")

    src = args.input or ask("Audio/video file")
    if not src or not os.path.isfile(src):
        print("[ERROR] File not found:", src)
        sys.exit(1)

    targets = list(args.targets)
    if not targets and sys.stdin.isatty():
        t = ask("Translate to (comma list, e.g. te,en,hi - Enter to skip)",
                default="")
        targets = [x.strip() for x in t.split(",") if x.strip()]
    for code in targets:
        if code not in LANG_NAMES:
            print(f"[WARN] Unknown language code '{code}'. Known: "
                  + ", ".join(sorted(LANG_NAMES)))

    outdir = ensure_output_dir()
    base = args.output or sanitize_filename(os.path.splitext(os.path.basename(src))[0])

    if args.lang and args.lang not in LANG_NAMES:
        print(f"[WARN] Unknown source code '{args.lang}', will auto-detect.")

    segs = transcribe(src, args.model, args.lang)
    segs = merge_segments(segs)
    print(f"[OK] {len(segs)} subtitle lines after merging.")

    srt_orig = os.path.join(outdir, base + ".srt")
    write_srt(segs, srt_orig)
    print("\n[OK] Original subtitles written to:", srt_orig)

    for code in targets:
        try:
            trans = translate_srt(segs, code)
            out_path = os.path.join(outdir, f"{base}.{code}.srt")
            write_srt(trans, out_path)
            print(f"[OK] Translated ({code}) written to:", out_path)
        except Exception as e:
            print(f"[ERROR] Translation to {code} failed: {e}")
            print("        This usually means no internet or Google blocking.")
    return 0


if __name__ == "__main__":
    main()