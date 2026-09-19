# AI YouTube Studio

A small collection of Python tools for making YouTube videos in **Telugu/Kuvi**
— lyric videos, thumbnails, subtitles, upload packages and audio cleanup.
Works on Windows; no coding needed to use it.

## First-time setup
1. Install Python from <https://www.python.org/downloads/> and tick
   **"Add Python to PATH"** during install.
2. Double-click **`setup.bat`** once (needs internet). It installs all
   packages, including `faster-whisper` for Tool 3.

## Start
Double-click **`studio.bat`** and pick a tool from the menu.
All output files are saved into the `output\` folder.

## Web UI (browser)
Double-click **`webapp.bat`** instead. It opens **http://127.0.0.1:8787** in your
browser — a SaaS-style dashboard with a sidebar, tool workspaces, live terminal
logs, run history and an output library for downloading finished files.
No extra packages needed.

## Deploy (run the website on a server)
The web UI only listens on **127.0.0.1** by default, so it is private. To run it
as a website after deploying:

```bash
# bind to all interfaces and pick a port (or set HOST / PORT env vars)
python webapp.py --host 0.0.0.0 --port 8787
```

- **Render (recommended)** — this repo ships a `render.yaml` Blueprint. On
  Render choose **New + → Blueprint → your repo** and click **Apply**. It
  creates the web service, installs ffmpeg + Telugu fonts, and mounts a
  persistent disk for outputs, run history and the Whisper model cache.
  Note: the free plan has ~512 MB RAM — use **Starter** or higher for
  Tool 3 (Whisper).
- **Docker** — build the image and run it (output + run history persist in volumes):
  ```bash
  docker build -t ai-studio .
  docker run -d --name ai-studio -p 8787:8787 \
    -v ai-studio-output:/app/output -v ai-studio-runs:/app/runs \
    --restart unless-stopped ai-studio
  ```
- **Linux VPS / systemd** — copy the project to `/opt/ai-studio`, then
  `sudo cp deploy/ai-studio.service /etc/systemd/system/` and
  `sudo systemctl enable --now ai-studio`. The site is on `http://<server-ip>:8787`.
- **Other PaaS (Railway / Fly.io)** — create a "Web Service" that runs
  `python webapp.py`; the platform sets `PORT` automatically, just
  add `HOST=0.0.0.0` to the environment.

Notes for servers:
- First Tool 3 run downloads the Whisper model into `runs\` (give it RAM/time).
- Put a reverse proxy (nginx/Caddy) in front if you want HTTPS and a real
  domain; the app itself needs no database.

## The 5 tools
| # | Tool | What it does |
|---|------|--------------|
| 1 | Auto Lyrics Video Maker | audio + lyrics (`.srt`/`.lrc`/`.txt`) → finished lyric video |
| 2 | AI Thumbnail Studio | title + subtitle/logo → 1280×720 thumbnail (PNG + JPG) |
| 3 | Auto Subtitle & Translation | speech → `.srt`, then translate it into Telugu/Hindi/etc. |
| 4 | Upload Package Generator | song title → ready-to-paste title options, description, tags |
| 5 | Audio Cleanup Assistant | denoise / loudness normalize / vocal removal / boost / convert |

Notes:
- Tool 3 needs an **internet connection** the first time (Whisper model
  download) and for translation (Google); Tool 4 works offline.
- Tools 1 and 5 need `ffmpeg`, which `setup.bat` installs.

## Command-line use (optional)
Each tool can also run by itself, e.g.:

```
python tools\tool1_lyrics_video.py --audio song.mp3 --lyrics song.srt
python tools\tool2_thumbnail_studio.py --title "యేసు నా రాజా"
python tools\tool3_subtitle_translate.py --input song.mp3 --targets te en hi
python tools\tool4_upload_package.py --title "యేసు నీ కార్యములు"
python tools\tool5_audio_cleanup.py --input song.mp3 --mode noise
```

Run `python studio.py` for the same menu as `studio.bat`.