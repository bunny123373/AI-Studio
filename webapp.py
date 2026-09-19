# -*- coding: utf-8 -*-
"""AI YouTube Studio - SaaS-style Web UI (standard library only).

Local product-style interface that drives the same 5 tools from a browser:
dashboard, tool workspaces, live terminal logs, run history and output
library. It listens on 127.0.0.1 by default; after deploying, bind it with
--host 0.0.0.0 (or set the HOST environment variable).

Run:   python webapp.py      (or double-click webapp.bat)
Open:  http://127.0.0.1:8787
"""
import argparse
import html
import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
# On a deployed service these can be pointed at a persistent disk mount.
OUTPUT_DIR = os.environ.get("AI_STUDIO_OUTPUT") or os.path.join(BASE_DIR, "output")
RUNS_DIR = os.environ.get("AI_STUDIO_RUNS") or os.path.join(BASE_DIR, "runs")
RUNS_INDEX = os.path.join(RUNS_DIR, "runs.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(RUNS_DIR, exist_ok=True)

RUNS = {}
RUNS_LOCK = threading.Lock()

TOOL_ICONS = {1: "\U0001f3b5", 2: "\U0001f5bc\ufe0f", 3: "\U0001f4ac",
              4: "\U0001f4e6", 5: "\U0001f39a\ufe0f"}


def _load_runs():
    try:
        with open(RUNS_INDEX, encoding="utf-8") as f:
            data = json.load(f)
        for rid, r in data.items():
            RUNS[rid] = r
    except (OSError, ValueError):
        pass


def _save_runs():
    with RUNS_LOCK:
        snap = dict(RUNS)
    try:
        with open(RUNS_INDEX, "w", encoding="utf-8") as f:
            json.dump(snap, f)
    except OSError:
        pass


# -------------------------------------------------------------------- tool specs
# fields: (name, label, kind, required, default, options, help)

TOOL_SPECS = {
    1: {
        "name": "Auto Lyrics Video Maker",
        "module": "tool1_lyrics_video.py",
        "desc": "Audio + lyrics (.srt/.lrc/.txt) into a finished lyric video.",
        "fields": [
            ("audio", "Song file path", "text", True, "", None,
             "mp3 / wav / m4a"),
            ("lyrics", "Lyrics file path", "text", True, "", None,
             ".srt / .lrc / .txt  \u2014 hint: samples/sample_lyrics.srt"),
            ("background", "Background video / image path", "text", False, "", None,
             "blank = animated colour background"),
            ("logo", "Channel logo image path", "text", False, "", None,
             "blank = no watermark"),
            ("res", "Video size WxH", "text", False, "1280x720", None, ""),
            ("fps", "Frames per second", "text", False, "30", None, ""),
            ("output", "Output file name", "text", False, "", None, "blank = auto"),
        ],
        "build": lambda v: (
            ["--audio", v.get("audio", "").strip(),
             "--lyrics", v.get("lyrics", "").strip(),
             "--background", v.get("background", "").strip(),
             "--logo", v.get("logo", "").strip(),
             "--res", v.get("res") or "1280x720",
             "--fps", v.get("fps") or "30"]
            + (["--output", v["output"]] if v.get("output") else [])
        ),
    },
    2: {
        "name": "AI Thumbnail Studio",
        "module": "tool2_thumbnail_studio.py",
        "desc": "Title + optional subtitle & logo into a 1280x720 thumbnail.",
        "fields": [
            ("title", "Title text", "text", True, "", None,
             "e.g. \u0c2f\u0c47\u0c38\u0c41 \u0c28\u0c3e \u0c30\u0c3e\u0c1c\u0c3e (Telugu/English)"),
            ("sub", "Small subtitle text", "text", False, "", None, "blank = none"),
            ("background", "Background image path", "text", False, "", None,
             "blank = auto colour"),
            ("logo", "Channel logo path", "text", False, "", None, "blank = none"),
            ("output", "Output file name", "text", False, "", None, "blank = auto"),
        ],
        "build": lambda v: (
            ["--title", v.get("title", "").strip(),
             "--sub", v.get("sub", "").strip(),
             "--background", v.get("background", "").strip(),
             "--logo", v.get("logo", "").strip()]
            + (["--output", v["output"]] if v.get("output") else [])
        ),
    },
    3: {
        "name": "Auto Subtitle & Translation",
        "module": "tool3_subtitle_translate.py",
        "desc": "Speech into .srt subtitles, optionally translated to several languages.",
        "fields": [
            ("input", "Audio / video file path", "text", True, "", None, ""),
            ("model", "Whisper model", "select", False, "small",
             ["tiny", "base", "small", "medium"], "bigger = more accurate, slower"),
            ("lang", "Source language code", "text", False, "", None,
             "e.g. te (Telugu), en \u2014 blank = auto"),
            ("targets", "Translate to codes", "text", False, "", None,
             "space separated, e.g. te en hi \u2014 blank = skip"),
            ("output", "Output base name", "text", False, "", None, "blank = auto"),
        ],
        "build": lambda v: (
            ["--input", v.get("input", "").strip(),
             "--model", v.get("model") or "small"]
            + (["--lang", v["lang"].strip()] if v.get("lang", "").strip() else [])
            + (["--targets"] + v["targets"].split()
               if v.get("targets", "").strip() else [])
            + (["--output", v["output"]] if v.get("output") else [])
        ),
    },
    4: {
        "name": "Upload Package Generator",
        "module": "tool4_upload_package.py",
        "desc": "Song title into paste-ready title options, description and tags.",
        "fields": [
            ("title", "Song title", "text", True, "", None,
             "e.g. \u0c2f\u0c47\u0c38\u0c41 \u0c28\u0c40 \u0c15\u0c3e\u0c30\u0c4d\u0c2f\u0c2e\u0c41\u0c32\u0c41"),
            ("channel", "Your channel name", "text", False, "Church of Christ", None, ""),
            ("notes", "Extra description text", "text", False, "", None, "blank = none"),
            ("extra-tags", "Extra tags", "text", False, "", None,
             "comma list \u2014 blank = none"),
            ("output", "Output file name", "text", False, "", None, "blank = auto"),
        ],
        "build": lambda v: (
            ["--title", v.get("title", "").strip(),
             "--channel", v.get("channel") or "Church of Christ"]
            + (["--notes", v["notes"].strip()] if v.get("notes", "").strip() else [])
            + (["--extra-tags", v["extra-tags"].strip()] if v.get("extra-tags", "").strip() else [])
            + (["--output", v["output"]] if v.get("output") else [])
        ),
    },
    5: {
        "name": "Audio Cleanup Assistant",
        "module": "tool5_audio_cleanup.py",
        "desc": "Denoise, loudness, vocal removal, boost or format convert.",
        "fields": [
            ("input", "Audio file path", "text", True, "", None, ""),
            ("mode", "Effect", "select", False, "noise",
             ["noise", "loud", "vocal", "boost", "convert"], ""),
            ("boost-db", "Gain in dB", "text", False, "5", None, "used by boost"),
            ("convert-ext", "Target format", "select", False, "mp3",
             ["mp3", "wav", "m4a", "ogg"], "used by convert"),
            ("output", "Output file name", "text", False, "", None, "blank = auto"),
        ],
        "build": lambda v: (
            ["--input", v.get("input", "").strip(),
             "--mode", v.get("mode") or "noise",
             "--boost-db", v.get("boost-db") or "5"]
            + (["--convert-ext", v.get("convert-ext") or "mp3"]
               if (v.get("mode") or "noise") == "convert" else [])
            + (["--output", v["output"]] if v.get("output") else [])
        ),
    },
}


# -------------------------------------------------------------------- run handling

def start_run(num, vals):
    spec = TOOL_SPECS.get(int(num))
    if not spec:
        return None
    mod_path = os.path.join(TOOLS_DIR, spec["module"])
    cmd = [sys.executable, "-u", mod_path] + spec["build"](vals)
    rid = uuid.uuid4().hex[:12]
    log_path = os.path.join(RUNS_DIR, rid + ".log")
    logf = open(log_path, "wb")
    proc = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=logf,
        stderr=subprocess.STDOUT, cwd=BASE_DIR)
    info = {"rid": rid, "num": int(num), "name": spec["name"],
            "start": time.time(), "done": False, "code": None}
    with RUNS_LOCK:
        RUNS[rid] = info

    def _wait():
        proc.wait()
        try:
            logf.close()
        except Exception:
            pass
        with RUNS_LOCK:
            RUNS[rid]["done"] = True
            RUNS[rid]["code"] = proc.returncode
        _save_runs()
    threading.Thread(target=_wait, daemon=True).start()
    return rid


def get_run(rid):
    with RUNS_LOCK:
        return RUNS.get(rid)


def log_text(rid):
    info = get_run(rid)
    if not info:
        return "", True, None
    try:
        with open(os.path.join(RUNS_DIR, rid + ".log"),
                  encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        text = ""
    return text, info.get("done", False), info.get("code")


def status_of(info):
    if not info.get("done"):
        return "running"
    return "success" if info.get("code") == 0 else "failed"


def list_outputs():
    try:
        names = os.listdir(OUTPUT_DIR)
    except OSError:
        return []
    out = []
    for n in names:
        p = os.path.join(OUTPUT_DIR, n)
        if os.path.isfile(p):
            out.append((os.path.getmtime(p), n, os.path.getsize(p)))
    out.sort(reverse=True)
    return out


def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


def fmt_ago(ts):
    d = time.time() - ts
    if d < 60:
        return "just now"
    if d < 3600:
        return f"{int(d // 60)} min ago"
    if d < 86400:
        return f"{int(d // 3600)} h ago"
    return f"{int(d // 86400)} d ago"


def ext_badge(name):
    ext = os.path.splitext(name)[1].lstrip(".").upper() or "FILE"
    return f"<span class=\"ext\">{html.escape(ext)}</span>"


# -------------------------------------------------------------------- html shell

CSS = """
:root{--nav:#141833;--nav2:#1c2145;--bg:#f3f5fb;--card:#fff;--line:#e5e8f2;
--ink:#171a2b;--muted:#6b7190;--acc:#6366f1;--acc2:#8b5cf6;--ok:#0e9f6e;--bad:#e0245c;--run:#b45309;}
*{box-sizing:border-box;}
body{margin:0;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--ink);}
a{color:var(--acc);text-decoration:none;}
.wrap{display:flex;min-height:100vh;}
.side{width:250px;background:linear-gradient(180deg,var(--nav),var(--nav2));color:#cdd3f0;padding:22px 14px;position:sticky;top:0;height:100vh;overflow:auto;flex-shrink:0;}
.brand{display:flex;align-items:center;gap:10px;padding:2px 8px 18px;}
.brand .mark{width:38px;height:38px;border-radius:11px;background:linear-gradient(135deg,var(--acc),var(--acc2));display:flex;align-items:center;justify-content:center;font-size:20px;color:#fff;}
.brand b{color:#fff;font-size:15px;display:block;line-height:1.15;}
.brand small{color:#8d93bd;font-size:11px;}
.nav{margin-top:6px;}
.nav .lbl{font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:#6d74a5;padding:14px 10px 6px;}
.nav a{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:9px;color:#cdd3f0;font-size:13.5px;margin:1px 0;}
.nav a:hover{background:rgba(255,255,255,.06);color:#fff;}
.nav a.on{background:linear-gradient(90deg,rgba(99,102,241,.32),rgba(139,92,246,.32));color:#fff;}
.nav a .ic{width:20px;text-align:center;}
.foot{margin-top:22px;padding:12px 10px;border-top:1px solid rgba(255,255,255,.08);font-size:11px;color:#8d93bd;}
.main{flex:1;padding:26px 34px 60px;min-width:0;}
.pagehead{display:flex;align-items:center;gap:14px;margin-bottom:18px;flex-wrap:wrap;}
.pagehead h1{font-size:22px;margin:0;}
.pagehead .sub{color:var(--muted);font-size:13.5px;margin-top:2px;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:16px;}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 1px 2px rgba(20,24,60,.04);}
.toolcard{display:flex;flex-direction:column;gap:10px;transition:transform .12s ease,box-shadow .12s ease;}
.toolcard:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(30,36,80,.10);}
.toolcard .t{display:flex;align-items:center;gap:12px;}
.toolcard .t .ic{width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg,#ececff,#f5edff);display:flex;align-items:center;justify-content:center;font-size:22px;}
.toolcard b{font-size:15px;}
.toolcard p{color:var(--muted);font-size:12.5px;margin:0;flex:1;line-height:1.5;}
.toolcard .open{align-self:flex-start;font-size:13px;font-weight:600;}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:24px;}
.stat{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;}
.stat .v{font-size:26px;font-weight:700;}
.stat .k{color:var(--muted);font-size:12px;margin-top:2px;}
h2.sec{font-size:15px;margin:26px 0 12px;letter-spacing:.01em;}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;}
th,td{text-align:left;padding:11px 14px;font-size:13px;border-bottom:1px solid var(--line);}
th{background:#fafbff;color:var(--muted);font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;}
tr:last-child td{border-bottom:0;}
.badge{display:inline-flex;align-items:center;gap:6px;padding:3px 11px;border-radius:20px;font-size:11.5px;font-weight:600;}
.badge::before{content:'';width:7px;height:7px;border-radius:50%;background:currentColor;}
.badge.running{background:#fff4e0;color:var(--run);}
.badge.running::before{animation:blink 1s infinite;}
.badge.success{background:#e6f7f0;color:var(--ok);}
.badge.failed{background:#ffecef;color:var(--bad);}
@keyframes blink{50%{opacity:.25}}
.ext{display:inline-block;background:#eef0fb;color:#52568a;border-radius:6px;padding:2px 7px;font-size:10.5px;font-weight:700;letter-spacing:.04em;margin-right:8px;}
.btn{display:inline-flex;align-items:center;gap:8px;border:0;border-radius:10px;padding:11px 20px;font-size:14px;font-weight:600;cursor:pointer;color:#fff;background:linear-gradient(135deg,var(--acc),var(--acc2));}
.btn:hover{filter:brightness(1.08);}
.btn.ghost{background:transparent;color:var(--acc);border:1px solid var(--line);}
label{display:block;margin:14px 0 5px;font-size:12.5px;font-weight:600;color:#3c4163;}
label .req{color:var(--bad);}
input,select{width:100%;padding:10px 12px;border-radius:10px;border:1px solid #d7dbee;background:#fff;color:var(--ink);font-size:14px;}
input:focus,select:focus{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px rgba(99,102,241,.15);}
.hint{font-size:11.5px;color:#8b90b4;margin-top:4px;}
.formcard{max-width:640px;}
.term{background:#0b0e1d;border:1px solid #1f2440;border-radius:12px;padding:14px;max-height:430px;overflow:auto;
font-family:Consolas,'Cascadia Mono',monospace;font-size:12.2px;line-height:1.55;color:#d7dcf4;white-space:pre-wrap;}
.files{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px;}
.fitem{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:12px 14px;display:flex;align-items:center;gap:10px;}
.fitem .meta{flex:1;min-width:0;}
.fitem .n{font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.fitem .s{font-size:11px;color:var(--muted);}
.fitem a{font-size:12px;font-weight:600;white-space:nowrap;}
.empty{color:var(--muted);font-size:13px;padding:26px;text-align:center;border:1px dashed #d7dbee;border-radius:12px;background:#fafbff;}
.bcrumb{font-size:13px;color:var(--muted);margin-bottom:14px;}
.bcrumb a{color:var(--acc);}
.mono{font-family:Consolas,monospace;}
"""


def page(page_id, title, body, active):
    nav_items = [
        ("/", "Dashboard", "\U0001f3e0"),
        ("/runs", "Run history", "\U0001f4cb"),
        ("/outputs", "Output library", "\U0001f4c1"),
    ]
    for num, spec in TOOL_SPECS.items():
        nav_items.append((f"/tool/{num}", f"Tool {num} \u2014 {spec['name']}",
                          TOOL_ICONS[num]))
    nav = []
    for href, label, ic in nav_items:
        cls = "on" if active == href else ""
        nav.append(f"<a href=\"{href}\" class=\"{cls}\"><span class=\"ic\">{ic}</span>{html.escape(label)}</a>")
    side = (
        "<aside class=\"side\"><div class=\"brand\">"
        "<div class=\"mark\">\U0001f3ac</div><div><b>AI YouTube Studio</b>"
        "<small>Creator workspace</small></div></div>"
        "<nav class=\"nav\"><div class=\"lbl\">Workspace</div>" + "".join(nav) +
        "<div class=\"foot\">Creator SaaS workspace<br>"
        "v1.1 \u00b7 runs on " + html.escape(page_id) + "</div></nav></aside>")
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{html.escape(title)} \u00b7 AI YouTube Studio</title>"
            f"<style>{CSS}</style></head><body><div class=\"wrap\">"
            + side + f"<main class=\"main\">{body}</main></div></body></html>")


def head(title, sub):
    return (f"<div class=\"pagehead\"><div><h1>{html.escape(title)}</h1>"
            f"<div class=\"sub\">{html.escape(sub) if sub else ''}</div></div></div>")


def status_badge(status):
    txt = {"running": "Running", "success": "Success", "failed": "Failed"}[status]
    return f"<span class=\"badge {status}\">{txt}</span>"


def output_blocks():
    items = list_outputs()
    if not items:
        return "<div class=\"empty\">Output folder is empty \u2014 run a tool to create files.</div>"
    blocks = []
    for _, name, size in items[:12]:
        blocks.append(
            f"<div class=\"fitem\">{ext_badge(name)}"
            f"<div class=\"meta\"><div class=\"n\">{html.escape(name)}</div>"
            f"<div class=\"s\">{fmt_size(size)}</div></div>"
            f"<a href=\"/output/{urllib.parse.quote(name)}\" download>Download</a></div>")
    return "<div class=\"files\">" + "".join(blocks) + "</div>"


def runs_table(rows):
    if not rows:
        return "<div class=\"empty\">No runs yet.</div>"
    trs = []
    for r in rows:
        st = status_of(r)
        trs.append(
            "<tr><td class=\"mono\">" + r["rid"] + "</td>"
            f"<td>{TOOL_ICONS.get(r['num'], '')} {html.escape(r['name'])}</td>"
            f"<td>{status_badge(st)}</td>"
            f"<td>{fmt_ago(r['start'])}</td>"
            f"<td><a href=\"/run/{r['rid']}\">View \u2192</a></td></tr>")
    return ("<table><thead><tr><th>Run</th><th>Tool</th><th>Status</th>"
            "<th>When</th><th></th></tr></thead><tbody>"
            + "".join(trs) + "</tbody></table>")


# -------------------------------------------------------------------- pages

def render_home():
    with RUNS_LOCK:
        runs = list(RUNS.values())
    total = len(runs)
    okc = sum(1 for r in runs if status_of(r) == "success")
    files = len(list_outputs())
    stats = (f"<div class=\"stats\">"
             f"<div class=\"stat\"><div class=\"v\">{total}</div><div class=\"k\">Total runs</div></div>"
             f"<div class=\"stat\"><div class=\"v\">{okc}</div><div class=\"k\">Successful</div></div>"
             f"<div class=\"stat\"><div class=\"v\">{files}</div><div class=\"k\">Output files</div></div>"
             "</div>")
    cards = []
    for num, spec in TOOL_SPECS.items():
        cards.append(
            f"<a class=\"card toolcard\" href=\"/tool/{num}\">"
            f"<div class=\"t\"><div class=\"ic\">{TOOL_ICONS[num]}</div>"
            f"<b>Tool {num} \u00b7 {html.escape(spec['name'])}</b></div>"
            f"<p>{html.escape(spec['desc'])}</p>"
            f"<span class=\"open\">Open workspace \u2192</span></a>")
    recent = sorted(runs, key=lambda r: r["start"], reverse=True)[:6]
    body = head("Dashboard", "Create videos, thumbnails, subtitles and more \u2014 all from your browser.")
    body += stats
    body += "<div class=\"grid\">" + "".join(cards) + "</div>"
    body += '<h2 class="sec">Recent runs</h2>' + runs_table(recent)
    body += '<h2 class="sec">Latest outputs</h2>' + output_blocks()
    return page("/", "Dashboard", body, "/")


def render_runs():
    with RUNS_LOCK:
        rows = sorted(RUNS.values(), key=lambda r: r["start"], reverse=True)
    body = head("Run history", "Every job started from this workspace.")
    body += runs_table(rows)
    return page("/runs", "Run history", body, "/runs")


def render_outputs():
    body = head("Output library", "Everything the tools produced, ready to download.")
    body += output_blocks()
    return page("/outputs", "Output library", body, "/outputs")


def render_form(num):
    spec = TOOL_SPECS.get(num)
    if not spec:
        return page("/", "Missing", "<div class=\"empty\">Unknown tool.</div>", "")
    fields = []
    for name, label, kind, required, default, options, help_txt in spec["fields"]:
        req = ' <span class="req">*</span>' if required else ""
        if kind == "select":
            opts = "".join(
                f"<option value=\"{o}\"{' selected' if o == (default or options[0]) else ''}>{o}</option>"
                for o in options)
            ctl = f"<select id=\"{name}\" name=\"{name}\">{opts}</select>"
        else:
            ctl = (f"<input type=\"text\" id=\"{name}\" name=\"{name}\" "
                   f"value=\"{html.escape(default or '')}\" "
                   f"placeholder=\"{html.escape(help_txt)}\">")
        hint = f"<div class=\"hint\">{html.escape(help_txt)}</div>" if help_txt else ""
        fields.append(f"<label for=\"{name}\">{html.escape(label)}{req}</label>{ctl}{hint}")
    body = head(f"Tool {num} \u00b7 {spec['name']}", spec["desc"])
    body += ("<div class=\"card formcard\"><form method=\"post\" action=\"/run\">"
             + "".join(fields)
             + f"<input type=\"hidden\" name=\"tool\" value=\"{num}\">"
             + "<div style=\"margin-top:8px\"><button class=\"btn\" type=\"submit\">"
             + "\u25b6 &nbsp;Start run</button> &nbsp; "
             + "<a class=\"btn ghost\" href=\"/\">Cancel</a></div></form></div>")
    body += '<h2 class="sec">Latest outputs</h2>' + output_blocks()
    return page(f"/tool/{num}", f"Tool {num}", body, f"/tool/{num}")


POLL_JS = """
<script>
async function poll(){
  try{
    const r=await fetch('/log/__RID__');
    const j=await r.json();
    const pre=document.getElementById('term');
    pre.textContent=j.text;
    pre.scrollTop=pre.scrollHeight;
    if(j.done){ location.href='/run/__RID__?done=1'; return; }
  }catch(e){}
  setTimeout(poll,1200);
}
poll();
</script>
"""


def render_run(rid, show_results):
    info = get_run(rid)
    if not info:
        return page("/", "Missing", "<div class=\"empty\">Run not found.</div>", "")
    text, done, code = log_text(rid)
    st = status_of(info)
    badge = status_badge(st)
    js = "" if done else POLL_JS.replace("__RID__", rid)
    results = ""
    if done and show_results:
        results = ('<h2 class="sec">Artifacts</h2>'
                   '<div class="muted" style="font-size:12.5px;margin-bottom:10px">'
                   "Exit code: " + (str(code) if code is not None else "?")
                   + "</div>" + output_blocks())
    body = ("<div class=\"bcrumb\"><a href=\"/\">Dashboard</a> / "
            f"<a href=\"/tool/{info['num']}\">{html.escape(info['name'])}</a>"
            f" / run {info['rid']}</div>")
    body += (f"<div class=\"pagehead\"><div><h1>Run {info['rid']} &nbsp;{badge}</h1>"
             f"<div class=\"sub\"><a href=\"/tool/{info['num']}\">Rerun this tool</a>"
             f" \u00b7 started {fmt_ago(info['start'])}</div></div></div>")
    body += "<h2 class=\"sec\">Live terminal</h2>"
    body += f"<div class=\"term\" id=\"term\">{html.escape(text[-50000:])}</div>"
    body += results + js
    return page(f"/run/{rid}", f"Run {rid[:6]}", body, "")


# -------------------------------------------------------------------- http server

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, text, code=200, ctype="text/html; charset=utf-8"):
        data = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj):
        self._send(json.dumps(obj), ctype="application/json")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/":
                self._send(render_home())
            elif path == "/runs":
                self._send(render_runs())
            elif path == "/outputs":
                self._send(render_outputs())
            elif path.startswith("/tool/"):
                try:
                    num = int(path.rsplit("/", 1)[1])
                except ValueError:
                    num = 0
                self._send(render_form(num))
            elif path.startswith("/run/"):
                rid = path.rsplit("/", 1)[1]
                self._send(render_run(rid, "done" in qs))
            elif path.startswith("/log/"):
                rid = path.rsplit("/", 1)[1]
                text, done, code = log_text(rid)
                self._send_json({"done": done, "text": text})
            elif path.startswith("/output/"):
                name = urllib.parse.unquote(path.split("/", 2)[2])
                self._serve_output(name)
            elif path in ("/healthz", "/health", "/ping"):
                self._send("ok", ctype="text/plain; charset=utf-8")
            elif path == "/shutdown":
                self._send("<p>Shutting down.</p>")
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self._send("<div class=\"empty\">Not found.</div>", 404)
        except BrokenPipeError:
            pass

    def _serve_output(self, name):
        name = os.path.basename(name)
        full = os.path.join(OUTPUT_DIR, name)
        if not os.path.isfile(full):
            self._send("<div class=\"empty\">File not found.</div>", 404)
            return
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition",
                         "attachment; filename*=UTF-8''"
                         + urllib.parse.quote(name))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8", "replace")
            vals = {k: v[-1] for k, v in urllib.parse.parse_qs(body).items()}
            num = vals.get("tool", "")
            rid = start_run(num, vals) if num else None
            if rid:
                self.send_response(302)
                self.send_header("Location", f"/run/{rid}")
                self.end_headers()
            else:
                self._send("<div class=\"empty\">Unknown tool.</div>", 400)
        except (ValueError, KeyError):
            self._send("<div class=\"empty\">Bad request.</div>", 400)


def main(argv=None):
    p = argparse.ArgumentParser(description="AI YouTube Studio Web UI")
    p.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"),
                   help="interface to bind (0.0.0.0 = exposed to the network)")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8787")))
    p.add_argument("--no-browser", action="store_true", help="do not open the browser")
    p.add_argument("--no-server", action="store_true",
                   help="print the tool URL and exit (for quick checks)")
    args = p.parse_args(argv)

    _load_runs()
    host = args.host
    local = host in ("127.0.0.1", "localhost", "::1")
    url = f"http://{host}:{args.port}"
    if args.no_server:
        print("Web UI would run at:", url)
        if not local:
            print("Bind to 0.0.0.0 (or set HOST) after deploying so it is reachable.")
        return 0

    server = ThreadingHTTPServer((host, args.port), Handler)
    print("\nAI YouTube Studio Web UI")
    print("Open in your browser:", url)
    if not local:
        print("Listening on all interfaces - make sure the firewall/security"
              " group allows this port.")
    print("Press Ctrl+C to stop the server.\n")
    if not args.no_browser and local:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        _save_runs()
    return 0


if __name__ == "__main__":
    main()