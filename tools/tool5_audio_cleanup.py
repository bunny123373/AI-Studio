# -*- coding: utf-8 -*-
"""Tool 5 - Audio Cleanup Assistant.

Uses ffmpeg's built-in filters (no heavy AI models needed):
  1. Noise reduction      - afftdn (denoiser)
  2. Loudness normalize   - loudnorm to -14 LUFS (YouTube standard)
  3. Vocal removal        - centre-channel extraction (karaoke style)
  4. Boost / volume       - simple gain
  5. Convert format       - mp3 / wav / m4a / ogg

Run standalone:  python tools/tool5_audio_cleanup.py --input song.mp3 --mode noise
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import ensure_output_dir, require_ffmpeg, sanitize_filename, ask, banner

MODES = {
    "noise":  "Noise reduction (denoise)",
    "loud":   "Loudness normalize (-14 LUFS)",
    "vocal":  "Vocal removal (karaoke)",
    "boost":  "Boost volume",
    "convert": "Convert file format",
}

EXT_BY_MODE = {
    "noise": ".mp3",
    "loud": ".mp3",
    "vocal": ".mp3",
    "boost": ".mp3",
    "convert": ".mp3",
}


def pick_mode(argv_mode):
    if argv_mode in MODES:
        return argv_mode
    print("Choose an effect:")
    for k, v in MODES.items():
        print(f"  {k:8s} - {v}")
    while True:
        choice = ask("Mode", default="noise").lower()
        if choice in MODES:
            return choice
        print("[WARN] Not a valid mode, try again.")


def run_ffmpeg(cmd, tag):
    ff = require_ffmpeg()
    print("\nRunning:", " ".join(cmd))
    try:
        r = subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error"] + cmd,
                           capture_output=True, text=True)
        if r.returncode != 0:
            print("[ERROR] ffmpeg failed:")
            print((r.stderr or r.stdout)[-1500:])
            sys.exit(1)
    except FileNotFoundError:
        print("[ERROR] Could not run ffmpeg at", ff)
        sys.exit(1)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audio Cleanup Assistant")
    parser.add_argument("--input", help="audio file")
    parser.add_argument("--mode", help="noise|loud|vocal|boost|convert")
    parser.add_argument("--output", help="output file name (optional)")
    parser.add_argument("--boost-db", type=float, default=5.0,
                        help="gain in dB for boost mode")
    parser.add_argument("--convert-ext", default="",
                        help="target format for convert mode (mp3/wav/m4a/ogg)")
    args = parser.parse_args(argv)

    banner("Tool 5 - Audio Cleanup Assistant")

    src = args.input or ask("Audio file (mp3/wav/m4a)")
    if not src or not os.path.isfile(src):
        print("[ERROR] File not found:", src)
        sys.exit(1)

    mode = pick_mode(args.mode)
    outdir = ensure_output_dir()
    base = args.output or sanitize_filename(
        os.path.splitext(os.path.basename(src))[0] + "_" + mode)
    ext = EXT_BY_MODE.get(mode, ".mp3")
    out_path = os.path.join(outdir, base + ext)

    if mode == "convert":
        ext = (args.convert_ext or "").lower() or ask(
            "Target format (mp3/wav/m4a/ogg)", default="mp3")
        if ext not in ("mp3", "wav", "m4a", "ogg"):
            print("[ERROR] Unsupported format:", ext)
            sys.exit(1)
        out_path = os.path.join(outdir, base + "." + ext)

    aopts = {"mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
             "wav": ["-c:a", "pcm_s16le"],
             "m4a": ["-c:a", "aac", "-b:a", "192k"],
             "ogg": ["-c:a", "libvorbis", "-q:a", "5"]}
    aenc = aopts.get(ext, aopts["mp3"])

    if mode == "noise":
        run_ffmpeg(["-i", src,
                    "-af", "afftdn=nf=-25,highpass=f=60,lowpass=f=15000",
                    "-map", "0:a:0"] + aenc + [out_path], "noise reduction")
    elif mode == "loud":
        run_ffmpeg(["-i", src,
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-map", "0:a:0"] + aenc + [out_path], "loudness normalize")
    elif mode == "vocal":
        run_ffmpeg(["-i", src,
                    "-af", "pan=stereo|c0=c0-c1|c1=c1-c0",
                    "-map", "0:a:0"] + aenc + [out_path], "vocal removal")
    elif mode == "boost":
        db = args.boost_db
        run_ffmpeg(["-i", src,
                    "-af", f"volume={db}dB,alimiter=limit=0.95",
                    "-map", "0:a:0"] + aenc + [out_path], "volume boost")
    elif mode == "convert":
        run_ffmpeg(["-i", src, "-map", "0:a:0"] + aenc + [out_path],
                   "convert")

    print("\n[OK] Saved to:", out_path)
    return 0


if __name__ == "__main__":
    main()