# -*- coding: utf-8 -*-
"""AI YouTube Studio - main launcher (run via studio.bat).

Menu that starts any of the 6 tools:

  1. Auto Lyrics Video Maker   audio + lyrics -> finished lyric video
  2. AI Thumbnail Studio       title -> YouTube thumbnail
  3. Auto Subtitle & Translation  speech -> .srt + translated subtitles
  4. Upload Package Generator  title -> YouTube title/description/tags
  5. Audio Cleanup Assistant   denoise / loudness / vocal-removal / convert
  6. AI Thumbnail Generator    free AI-generated art + title overlay
"""
import importlib
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(BASE_DIR, "tools")


def setup_path():
    """Make the tools/ folder importable from studio.py."""
    if TOOLS_DIR not in sys.path:
        sys.path.insert(0, TOOLS_DIR)


TOOLS = [
    {"num": 1, "name": "Auto Lyrics Video Maker",
     "module": "tool1_lyrics_video", "needs_ffmpeg": True},
    {"num": 2, "name": "AI Thumbnail Studio",
     "module": "tool2_thumbnail_studio", "needs_ffmpeg": False},
    {"num": 3, "name": "Auto Subtitle & Translation",
     "module": "tool3_subtitle_translate", "needs_ffmpeg": False},
    {"num": 4, "name": "Upload Package Generator",
     "module": "tool4_upload_package", "needs_ffmpeg": False},
    {"num": 5, "name": "Audio Cleanup Assistant",
     "module": "tool5_audio_cleanup", "needs_ffmpeg": True},
    {"num": 6, "name": "AI Thumbnail Generator (free AI art)",
     "module": "tool6_ai_thumbnail", "needs_ffmpeg": False},
]


def main():
    setup_path()
    from common import banner, find_ffmpeg, ensure_output_dir

    ensure_output_dir()
    print("\nAI YouTube Studio - make Telugu/Kuvi YouTube content: songs,")
    print("thumbnails, subtitles, upload packages and clean audio.")

    while True:
        print("\n" + "=" * 60)
        print("  MAIN MENU")
        print("=" * 60)
        for t in TOOLS:
            exists = os.path.isfile(os.path.join(TOOLS_DIR, t["module"] + ".py"))
            mark = "" if exists else "   [NOT BUILT]"
            print(f"  {t['num']}  {t['name']}{mark}")
        print("  0  Exit")
        print("  ffmpeg :", "OK" if find_ffmpeg() else "NOT FOUND - run setup.bat")

        choice = input("\nChoose a tool [1-6, 0] : ").strip()
        if choice == "0":
            print("Goodbye!")
            return 0
        if not choice.isdigit():
            continue
        sel = [t for t in TOOLS if str(t["num"]) == choice]
        if not sel:
            continue
        tool = sel[0]
        mod_path = os.path.join(TOOLS_DIR, tool["module"] + ".py")
        if not os.path.isfile(mod_path):
            print(f"\n[ERROR] {tool['module']}.py is missing (not built yet).")
            input("Press Enter to continue...")
            continue
        if tool["needs_ffmpeg"] and not find_ffmpeg():
            print("\n[ERROR] ffmpeg was not found. Run setup.bat once to install it.")
            input("Press Enter to continue...")
            continue
        try:
            mod = importlib.import_module(tool["module"])
            mod.main([])
        except KeyboardInterrupt:
            print("\n(Cancelled.)")
        except Exception as e:
            print(f"\n[ERROR] {type(e).__name__}: {e}")
        input("\nPress Enter to return to the menu...")


if __name__ == "__main__":
    main()