# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import subprocess, os, datetime, tempfile, json, re, time, random, uuid
import zipfile, io, traceback, requests, threading, shutil, hashlib
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Resolve tool paths (works even when Streamlit strips PATH) ──────────
def _find_bin(name):
    """Return full path of a binary, checking common locations."""
    candidates = [
        f"/opt/homebrew/bin/{name}",      # macOS Apple Silicon
        f"/usr/local/bin/{name}",          # macOS Intel / Linux
        f"/usr/bin/{name}",
        name,                              # fallback: rely on PATH
    ]
    # ffmpeg/ffprobe use -version (single dash), yt-dlp uses --version
    version_flag = "-version" if name in ("ffmpeg", "ffprobe") else "--version"
    for p in candidates:
        try:
            r = subprocess.run([p, version_flag], capture_output=True, timeout=5)
            if r.returncode == 0:
                return p
        except Exception:
            continue
    return name  # last resort

YTDLP   = _find_bin("yt-dlp")
FFMPEG  = _find_bin("ffmpeg")
FFPROBE = _find_bin("ffprobe")

st.set_page_config(
    page_title="TikTok Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Brand system ────────────────────────────────────────────────────────
# Duotone: TikTok cyan (#25F4EE) + magenta (#FE2C55) on a near-black base.
# Cyan carries interaction (focus, hover, progress), magenta carries
# identity and primary actions; everything else stays neutral so the two
# accents never compete.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root{
  --ts-bg:#08090D; --ts-surface:#12141C; --ts-surface2:#191C26;
  --ts-border:#262A38; --ts-border-lit:#333949;
  --ts-text:#ECEEF4; --ts-muted:#8A91A6;
  --ts-cyan:#25F4EE; --ts-pink:#FE2C55;
  --ts-grad:linear-gradient(120deg,#25F4EE 0%,#48C6EF 42%,#FE2C55 100%);
  --ts-font:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',sans-serif;
  --ts-r:14px;
}

.stApp{background:var(--ts-bg);}
html,body,.stApp,[class*="css"]{font-family:var(--ts-font)!important;color:var(--ts-text);}
[data-testid="stHeader"]{background:transparent;}
[data-testid="stDecoration"]{background:var(--ts-grad);height:3px;}
.block-container{padding-top:2.2rem;max-width:1500px;}

/* ── Hero ─────────────────────────────────────────────── */
.ts-hero{display:flex;align-items:center;gap:20px;flex-wrap:wrap;
  padding:26px 30px;margin-bottom:20px;border-radius:20px;
  background:radial-gradient(1200px 240px at 0% 0%,rgba(37,244,238,.10),transparent 60%),
             radial-gradient(900px 240px at 100% 100%,rgba(254,44,85,.12),transparent 60%),
             var(--ts-surface);
  border:1px solid var(--ts-border);}
.ts-mark{width:56px;height:56px;flex:0 0 56px;border-radius:17px;display:grid;place-items:center;
  font-size:28px;background:var(--ts-grad);box-shadow:0 8px 26px rgba(254,44,85,.28);}
.ts-name{font-size:2.05rem;font-weight:800;letter-spacing:-.028em;line-height:1.1;margin:0;}
.ts-name span{background:var(--ts-grad);-webkit-background-clip:text;background-clip:text;
  -webkit-text-fill-color:transparent;}
.ts-tag{margin:5px 0 0;color:var(--ts-muted);font-size:.95rem;font-weight:450;}
.ts-tag b{color:var(--ts-text);font-weight:600;}
.ts-pill{margin-left:auto;padding:7px 15px;border-radius:999px;font-size:.72rem;font-weight:700;
  letter-spacing:.10em;color:var(--ts-cyan);background:rgba(37,244,238,.09);
  border:1px solid rgba(37,244,238,.28);white-space:nowrap;}

/* ── Tabs ─────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"]{gap:8px;flex-wrap:wrap;background:transparent;
  border-bottom:1px solid var(--ts-border);padding-bottom:12px;margin-bottom:8px;}
.stTabs [data-baseweb="tab"]{height:auto;padding:10px 17px;border-radius:11px;
  background:var(--ts-surface);border:1px solid var(--ts-border);
  color:var(--ts-muted)!important;font-weight:600;font-size:.9rem;letter-spacing:-.01em;
  transition:all .16s ease;}
.stTabs [data-baseweb="tab"]:hover{background:var(--ts-surface2);color:var(--ts-text)!important;
  border-color:var(--ts-border-lit);transform:translateY(-1px);}
.stTabs [aria-selected="true"]{background:var(--ts-grad)!important;border-color:transparent!important;
  color:#06080C!important;font-weight:700;box-shadow:0 6px 20px rgba(37,244,238,.18);}
.stTabs [aria-selected="true"] p{color:#06080C!important;font-weight:700;}
.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{display:none;}

/* ── Type ─────────────────────────────────────────────── */
h1,h2,h3{letter-spacing:-.022em;font-weight:700;}
h2{font-size:1.55rem;margin-top:.3rem;}
h3{font-size:1.07rem;color:var(--ts-text);padding-left:12px;position:relative;margin-top:1.5rem;}
h3::before{content:"";position:absolute;left:0;top:.22em;bottom:.22em;width:3px;
  border-radius:3px;background:var(--ts-grad);}
hr{border-color:var(--ts-border);}
a{color:var(--ts-cyan)!important;}

/* ── Buttons ──────────────────────────────────────────── */
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{
  border-radius:11px;font-weight:600;font-size:.9rem;padding:.55rem 1.1rem;
  background:var(--ts-surface2);color:var(--ts-text);border:1px solid var(--ts-border-lit);
  transition:all .16s ease;}
.stButton>button:hover,.stDownloadButton>button:hover,.stFormSubmitButton>button:hover{
  border-color:var(--ts-cyan);color:var(--ts-cyan);transform:translateY(-1px);
  box-shadow:0 5px 18px rgba(37,244,238,.12);}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{
  background:var(--ts-grad);color:#06080C;border:none;font-weight:700;
  box-shadow:0 6px 22px rgba(254,44,85,.26);}
.stButton>button[kind="primary"]:hover,.stFormSubmitButton>button[kind="primary"]:hover{
  filter:brightness(1.09);color:#06080C;transform:translateY(-1px);
  box-shadow:0 9px 30px rgba(254,44,85,.36);}
.stButton>button:disabled,.stDownloadButton>button:disabled{opacity:.4;transform:none;box-shadow:none;}

/* ── Inputs ───────────────────────────────────────────── */
.stTextInput input,.stTextArea textarea,.stNumberInput input,
[data-baseweb="select"]>div,[data-baseweb="input"]{
  background:var(--ts-surface)!important;border:1px solid var(--ts-border)!important;
  border-radius:11px!important;color:var(--ts-text)!important;}
.stTextInput input:focus,.stTextArea textarea:focus,.stNumberInput input:focus{
  border-color:var(--ts-cyan)!important;box-shadow:0 0 0 3px rgba(37,244,238,.13)!important;}
[data-baseweb="select"]>div:hover{border-color:var(--ts-border-lit)!important;}
.stTextArea textarea{font-size:.95rem;line-height:1.65;}
label,.stMarkdown p{color:var(--ts-text);}
[data-testid="stWidgetLabel"] p{font-weight:600;font-size:.87rem;color:var(--ts-text);}
[data-testid="stCaptionContainer"],small{color:var(--ts-muted)!important;}

/* ── Uploader ─────────────────────────────────────────── */
[data-testid="stFileUploaderDropzone"]{background:var(--ts-surface);
  border:1.5px dashed var(--ts-border-lit);border-radius:var(--ts-r);transition:all .18s ease;}
[data-testid="stFileUploaderDropzone"]:hover{border-color:var(--ts-cyan);
  background:rgba(37,244,238,.035);}

/* ── Slider / progress ────────────────────────────────── */
.stSlider [data-baseweb="slider"] div[role="slider"]{background:var(--ts-cyan)!important;
  border:2px solid #06080C!important;box-shadow:0 0 0 4px rgba(37,244,238,.18)!important;}
.stProgress>div>div>div>div{background:var(--ts-grad);}
.stProgress>div>div>div{background:var(--ts-surface2);border-radius:999px;}

/* ── Feedback ─────────────────────────────────────────── */
[data-testid="stAlert"],.stAlert{border-radius:12px;border:1px solid var(--ts-border);
  border-left-width:3px;background:var(--ts-surface);}
[data-testid="stExpander"]{border:1px solid var(--ts-border);border-radius:12px;
  background:var(--ts-surface);overflow:hidden;}
[data-testid="stExpander"] summary:hover{color:var(--ts-cyan);}
[data-testid="stMetric"]{background:var(--ts-surface);border:1px solid var(--ts-border);
  border-radius:12px;padding:14px 16px;}
[data-testid="stMetricValue"]{background:var(--ts-grad);-webkit-background-clip:text;
  background-clip:text;-webkit-text-fill-color:transparent;font-weight:800;}
.stCheckbox,.stRadio{color:var(--ts-text);}
code{background:var(--ts-surface2)!important;color:var(--ts-cyan)!important;
  border:1px solid var(--ts-border);border-radius:6px;padding:1px 6px;font-size:.86em;}
[data-testid="stCodeBlock"] code{border:none;color:var(--ts-text)!important;}
img{border-radius:10px;}
audio{width:100%;filter:saturate(1.15);}

/* Arabic scripts read right-to-left on their own */
.stTextArea textarea{unicode-bidi:plaintext;}

::-webkit-scrollbar{width:10px;height:10px;}
::-webkit-scrollbar-track{background:var(--ts-bg);}
::-webkit-scrollbar-thumb{background:var(--ts-border-lit);border-radius:8px;}
::-webkit-scrollbar-thumb:hover{background:var(--ts-muted);}

@media (max-width:760px){
  .ts-hero{padding:20px;gap:14px;} .ts-name{font-size:1.6rem;}
  .ts-pill{margin-left:0;} .block-container{padding-top:1.2rem;}
}
</style>
""", unsafe_allow_html=True)

def render_hero(title, tagline, tool_count):
    head, _, tail = title.rpartition(" ")
    if not head:
        head, tail = title, ""
    st.markdown(
        f'<div class="ts-hero">'
        f'  <div class="ts-mark">🎬</div>'
        f'  <div>'
        f'    <h1 class="ts-name">{head} <span>{tail}</span></h1>'
        f'    <p class="ts-tag">{tagline}</p>'
        f'  </div>'
        f'  <div class="ts-pill">{tool_count} TOOLS</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ── Configuration & admin ───────────────────────────────────────────────
# Everything the admin can change lives in one JSON file. It holds API keys,
# so it is gitignored and must never be committed.
CONFIG_FILE = "studio_config.json"

TOOL_REGISTRY = [
    ("downloader",   "📥 TikTok Downloader"),
    ("variants",     "🎛️ Variant Generator"),
    ("metadata",     "🔄 Refresh Metadata"),
    ("find_similar", "🔍 Find Similar"),
    ("audio",        "🎵 Extract Audio"),
    ("text",         "📝 Extract Text"),
    ("design",       "🎨 Design Studio"),
    ("voice",        "🗣️ Saudi Voice"),
]

def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def default_config():
    return {
        "admin": {"username": "BAHIM", "password_hash": _sha("BAHIM")},
        "api":   {"groq_api_key": "", "serpapi_key": ""},
        "params": {
            "tts_model":         "canopylabs/orpheus-arabic-saudi",
            "tts_default_voice": "fahad",
            "tts_chunk_chars":   550,
            "tts_gap_ms":        140,
            "meta_days_back":    10,
            "design_preset":     "Strong (recommended)",
            "app_title":         "TikTok Studio",
            "app_tagline":       "Download · Remix · Localize · Design · Voice — your whole content pipeline in one place",
        },
        "tools": {k: True for k, _ in TOOL_REGISTRY},
    }

def load_config():
    cfg = default_config()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        for section, values in saved.items():
            if isinstance(values, dict) and isinstance(cfg.get(section), dict):
                cfg[section].update(values)
            else:
                cfg[section] = values
    except Exception:
        pass                      # first run, or an unreadable file -> defaults
    for k, _ in TOOL_REGISTRY:    # a tool added in a later version defaults to on
        cfg["tools"].setdefault(k, True)
    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
    try:
        os.chmod(CONFIG_FILE, 0o600)     # it holds API keys
    except Exception:
        pass

CFG = load_config()
PARAMS = CFG["params"]

def cfg_api_key(name, *env_names):
    """Admin dashboard value wins, then st.secrets, then the environment."""
    v = CFG["api"].get(name, "")
    if v:
        return v, "admin dashboard"
    for src in env_names:
        try:
            v = st.secrets.get(src, "")
            if v:
                return v, "secrets"
        except Exception:
            pass
        v = os.environ.get(src, "")
        if v:
            return v, "environment"
    return "", "none"

render_hero(PARAMS.get("app_title", "TikTok Studio"),
            PARAMS.get("app_tagline", ""),
            sum(1 for k, _ in TOOL_REGISTRY if CFG["tools"].get(k, True)))

# Tabs are built from the tools the admin left enabled. Anything disabled is
# routed into a trailing sink tab whose button is hidden, so the existing
# `with tabN:` blocks keep working untouched.
_enabled  = [(k, lbl) for k, lbl in TOOL_REGISTRY if CFG["tools"].get(k, True)]
_disabled = len(_enabled) < len(TOOL_REGISTRY)
_labels   = [lbl for _, lbl in _enabled] + ["⚙️ Admin"] + (["·"] if _disabled else [])
_tab_objs = st.tabs(_labels)

_slot     = {k: _tab_objs[i] for i, (k, _) in enumerate(_enabled)}
admin_tab = _tab_objs[len(_enabled)]
_sink     = _tab_objs[-1] if _disabled else admin_tab

if _disabled:
    # the sink is the last tab; the highlight bar is a DIV, so :last-of-type
    # among the buttons always lands on it
    st.markdown(
        '<style>.stTabs [data-baseweb="tab-list"] '
        'button[data-baseweb="tab"]:last-of-type{display:none!important;}</style>',
        unsafe_allow_html=True,
    )

def _T(key):
    return _slot.get(key, _sink)

tab1, tab2, tab3, tab4 = _T("downloader"), _T("variants"), _T("metadata"), _T("find_similar")
tab5, tab6, tab7, tab8 = _T("audio"), _T("text"), _T("design"), _T("voice")


# ============================================================
# TAB 1 — TikTok Downloader (converted from Flask)
# ============================================================
with tab1:
    st.header("📥 TikTok Video Extractor & Downloader")
    st.markdown("Extract videos from any TikTok profile/hashtag URL, select the ones you want, and download them as a ZIP.")

    # ---- helpers ----
    def format_number(num):
        if not num:
            return "N/A"
        try:
            num = int(num)
        except (ValueError, TypeError):
            return str(num)
        if num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num/1_000:.1f}K"
        return str(num)

    def check_ytdlp():
        try:
            r = subprocess.run([YTDLP, "--version"], capture_output=True, text=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    def extract_with_ytdlp(url):
        cmd = [
            YTDLP,
            "--dump-json",
            "--flat-playlist",
            "--no-warnings",
            "--no-check-certificate",
            "--extractor-retries", "3",
            "--playlist-end", "9999",   # no artificial limit
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        videos = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                info = json.loads(line)
                video_url = info.get("webpage_url") or info.get("url") or ""
                vid_id    = info.get("id", "")
                if not vid_id:
                    continue
                videos.append({
                    "id":        vid_id,
                    "title":     info.get("title", "TikTok Video"),
                    "thumbnail": info.get("thumbnail", ""),
                    "views":     format_number(info.get("view_count", 0)),
                    "likes":     format_number(info.get("like_count", 0)),
                    "url":       video_url,
                })
            except json.JSONDecodeError:
                continue
        return videos

    def _find_completed_file(vid_dir, vid_id):
        """Return path of a fully-downloaded file for vid_id, or None."""
        if not os.path.isdir(vid_dir):
            return None
        for fname in os.listdir(vid_dir):
            if fname.startswith(vid_id) and not fname.endswith((".part", ".ytdl", ".tmp")):
                fpath = os.path.join(vid_dir, fname)
                if os.path.getsize(fpath) > 0:
                    return fpath
        return None

    def _download_one(vid_id, vid_url, output_dir, start_delay=0):
        """Download a single video into its own subdirectory. Returns (vid_id, filepath|None, err|None)."""
        vid_dir = os.path.join(output_dir, vid_id)

        # Resume support: already fully downloaded in a previous run → skip instantly
        existing = _find_completed_file(vid_dir, vid_id)
        if existing:
            return vid_id, existing, None

        if start_delay:
            time.sleep(start_delay)

        os.makedirs(vid_dir, exist_ok=True)
        output_template = os.path.join(vid_dir, f"{vid_id}.%(ext)s")

        FORMAT_ATTEMPTS = ["bestvideo+bestaudio/best", "best", "worst"]
        last_err = ""

        for fmt in FORMAT_ATTEMPTS:
            cmd = [
                YTDLP, "-f", fmt,
                "--merge-output-format", "mp4",
                "--no-warnings", "--no-check-certificate",
                "--extractor-retries", "5",
                "--retries", "10",
                "--fragment-retries", "10",
                "--retry-sleep", "3",
                "--sleep-requests", "1",
                "-o", output_template,
                vid_url,
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=240)
            except subprocess.TimeoutExpired:
                last_err = "timed out after 240s"
                time.sleep(2)
                continue

            if result.returncode == 0:
                fpath = _find_completed_file(vid_dir, vid_id)
                if fpath:
                    return vid_id, fpath, None
                last_err = "file missing after download"
            else:
                last_err = result.stderr.decode(errors="replace")[-300:] if result.stderr else "unknown error"

            time.sleep(1.5)

        return vid_id, None, last_err

    def download_videos_ytdlp(video_list, output_dir, progress_bar, status_text, max_workers=5):
        """Parallel download: runs up to max_workers videos simultaneously."""
        downloaded = []
        failed = []
        total = len(video_list)
        completed = 0
        lock = threading.Lock()

        # Build id → url from the list itself (falls back to session state)
        id_to_url = {}
        for v in video_list:
            if isinstance(v, dict) and v.get("url"):
                id_to_url[v["id"]] = v["url"]
        for v in st.session_state.get("dl_videos", []):
            id_to_url.setdefault(v["id"], v["url"])

        status_text.markdown(
            f"⬇️ Downloading **{total}** videos — **{max_workers} parallel workers**"
        )
        progress_bar.progress(0)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _download_one,
                    (vid if isinstance(vid, str) else vid["id"]),
                    id_to_url.get(
                        (vid if isinstance(vid, str) else vid["id"]),
                        f"https://www.tiktok.com/@x/video/{(vid if isinstance(vid, str) else vid['id'])}"
                    ),
                    output_dir,
                    # small random jitter so parallel workers don't hit TikTok
                    # at the exact same instant (never grows with batch size)
                    random.uniform(0.1, 1.0) if i else 0,
                ): vid
                for i, vid in enumerate(video_list)
            }

            for future in as_completed(futures):
                try:
                    vid_id, fpath, err = future.result()
                except Exception as exc:
                    vid_id = "unknown"
                    fpath, err = None, str(exc)

                with lock:
                    completed += 1
                    if fpath:
                        downloaded.append(fpath)
                    else:
                        failed.append((vid_id, err or "unknown error"))

                    progress_bar.progress(completed / total)
                    status_text.markdown(
                        f"⬇️ **{completed}/{total}** complete"
                        + (f" — ✅ {len(downloaded)} OK" if downloaded else "")
                        + (f" — ⚠️ {len(failed)} failed" if failed else "")
                    )

        if failed:
            status_text.markdown(
                f"⚠️ **{len(failed)}/{total}** video(s) failed: "
                + ", ".join(f"`{vid_id}`" for vid_id, _ in failed)
            )

        return downloaded, failed

    # ---- Persistent batches (survive sleep / connection loss / restart) ----
    DL_ROOT = os.path.expanduser("~/.tiktok_studio_downloads")

    def dl_save_manifest(batch_dir, manifest):
        os.makedirs(batch_dir, exist_ok=True)
        with open(os.path.join(batch_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f)

    def dl_load_manifest(batch_dir):
        try:
            with open(os.path.join(batch_dir, "manifest.json")) as f:
                return json.load(f)
        except Exception:
            return None

    def dl_list_batches():
        batches = []
        if os.path.isdir(DL_ROOT):
            for name in sorted(os.listdir(DL_ROOT), reverse=True):
                bdir = os.path.join(DL_ROOT, name)
                m = dl_load_manifest(bdir)
                if m:
                    batches.append((bdir, m))
        return batches

    def dl_count_completed(batch_dir, video_ids):
        return sum(
            1 for vid_id in video_ids
            if _find_completed_file(os.path.join(batch_dir, vid_id), vid_id)
        )

    def dl_execute_batch(batch_dir, manifest):
        """Download all videos of a batch (skipping ones already on disk), then offer the ZIP.
        Files stay on disk until everything succeeds, so an interrupted run can resume."""
        videos = manifest["videos"]
        total = len(videos)
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            downloaded, failed = download_videos_ytdlp(
                videos, batch_dir, progress_bar, status_text,
                max_workers=manifest.get("workers", 5),
            )

            if downloaded:
                # Write the ZIP to disk — it survives reruns/restarts, and the
                # persistent "Ready ZIPs" section serves it reliably.
                zip_path = os.path.join(
                    DL_ROOT, f"tiktok_videos_{os.path.basename(batch_dir)}.zip"
                )
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for fp in downloaded:
                        zf.write(fp, os.path.basename(fp))

                progress_bar.progress(1.0)

                if failed:
                    # Keep the batch resumable so failed ones can be retried,
                    # remember the errors for display
                    manifest["last_failed"] = [[vid_id, err] for vid_id, err in failed]
                    dl_save_manifest(batch_dir, manifest)
                else:
                    # Complete — mark done and free the disk space (ZIP is kept)
                    manifest["status"] = "done"
                    dl_save_manifest(batch_dir, manifest)
                    shutil.rmtree(batch_dir, ignore_errors=True)

                # Rerun so the persistent ZIP section at the top shows the file
                st.rerun()
            else:
                status_text.error(
                    "No videos downloaded. Progress is saved — "
                    "check your connection and click **Resume** to continue."
                )
                if failed:
                    with st.expander("Error details"):
                        for vid_id, err in failed:
                            st.markdown(f"**{vid_id}**: {err}")
        except Exception as e:
            status_text.error(
                f"Download interrupted: {e} — progress is saved, use **Resume** to continue."
            )

    # ---- Resume unfinished batches ----
    dl_unfinished = [(d, m) for d, m in dl_list_batches() if m.get("status") != "done"]
    if dl_unfinished:
        st.markdown("### ⏯️ Unfinished downloads")
        st.caption(
            "These batches were interrupted (sleep, lost connection, closed app). "
            "Already-downloaded videos are saved — Resume only downloads what's missing."
        )
        for bdir, m in dl_unfinished:
            batch_name = os.path.basename(bdir)
            vid_ids = [v["id"] for v in m.get("videos", [])]
            done_count = dl_count_completed(bdir, vid_ids)
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.markdown(
                    f"📦 **{batch_name}** — {done_count}/{len(vid_ids)} downloaded, "
                    f"{len(vid_ids) - done_count} remaining"
                )
            with c2:
                resume_clicked = st.button("▶️ Resume", key=f"resume_{batch_name}", use_container_width=True)
            with c3:
                if st.button("🗑️ Delete", key=f"delbatch_{batch_name}", use_container_width=True):
                    shutil.rmtree(bdir, ignore_errors=True)
                    st.rerun()
            if resume_clicked:
                dl_execute_batch(bdir, m)
            if m.get("last_failed"):
                with st.expander(f"⚠️ {len(m['last_failed'])} video(s) failed last run — details"):
                    for vid_id, err in m["last_failed"]:
                        st.markdown(f"**{vid_id}**: {err}")
        st.markdown("---")

    # ---- Ready ZIPs (persistent — the download link never dies on rerun) ----
    dl_ready_zips = []
    if os.path.isdir(DL_ROOT):
        dl_ready_zips = sorted(
            (f for f in os.listdir(DL_ROOT) if f.endswith(".zip")),
            reverse=True,
        )
    if dl_ready_zips:
        st.markdown("### 📦 Ready ZIPs")
        for zip_name in dl_ready_zips:
            zip_path = os.path.join(DL_ROOT, zip_name)
            try:
                size_mb = os.path.getsize(zip_path) / (1024 * 1024)
            except OSError:
                continue
            z1, z2 = st.columns([4, 1])
            with z1:
                with open(zip_path, "rb") as fzip:
                    st.download_button(
                        label=f"⬇️ {zip_name} ({size_mb:.0f} MB)",
                        data=fzip,
                        file_name=zip_name,
                        mime="application/zip",
                        key=f"zipdl_{zip_name}",
                        use_container_width=True,
                    )
            with z2:
                if st.button("🗑️ Delete", key=f"zipdel_{zip_name}", use_container_width=True):
                    try:
                        os.unlink(zip_path)
                    except Exception:
                        pass
                    st.rerun()
        st.markdown("---")

    # ---- UI state ----
    if "dl_videos" not in st.session_state:
        st.session_state.dl_videos = []
    if "dl_selected" not in st.session_state:
        st.session_state.dl_selected = set()

    # ---- Step 1: Extract ----
    st.subheader("Step 1 — Extract Videos")
    col_url, col_btn = st.columns([4, 1])
    with col_url:
        tiktok_url = st.text_input(
            "TikTok URL",
            placeholder="https://www.tiktok.com/@username or hashtag URL",
            label_visibility="collapsed"
        )
    with col_btn:
        extract_btn = st.button("🔍 Extract", use_container_width=True)

    if extract_btn:
        if not tiktok_url:
            st.error("Please enter a TikTok URL.")
        elif "tiktok.com" not in tiktok_url:
            st.error("Please enter a valid TikTok URL.")
        elif not check_ytdlp():
            st.error("yt-dlp is not installed. Run: `pip install yt-dlp`")
        else:
            with st.spinner("Extracting videos..."):
                try:
                    videos = extract_with_ytdlp(tiktok_url)
                    if videos:
                        for _k in [k for k in st.session_state if k.startswith("dlpick_")]:
                            del st.session_state[_k]
                        st.session_state.dl_videos = videos
                        st.session_state.dl_selected = set()
                        st.success(f"✅ Found **{len(videos)}** videos!")
                    else:
                        st.warning("No videos found. Check the URL and make sure the profile is public.")
                except Exception as e:
                    st.error(f"Extraction failed: {e}")

    # ---- Step 2: Select ----
    if st.session_state.dl_videos:
        st.markdown("---")
        st.subheader("Step 2 — Select Videos")
        st.caption(
            "Click a card to toggle it · **drag a box** across the grid to grab many at once · "
            "**Shift-click** for a range · hold **Alt** while dragging to deselect. "
            "Nothing reloads until you hit Download."
        )

        videos = st.session_state.dl_videos

        # Selection state lives in the checkbox widgets themselves. Seed them
        # once per extraction so a fresh URL doesn't inherit stale ticks.
        for _v in videos:
            st.session_state.setdefault(f"dlpick_{_v['id']}", _v["id"] in st.session_state.dl_selected)

        st.markdown("""
<style>
/* the card lights up straight from the checkbox state — no round trip */
[data-testid="stColumn"]:has(.dl-card),[data-testid="column"]:has(.dl-card){position:relative;}
.dl-card{border:2px solid var(--ts-border);border-radius:12px;padding:10px;
  margin-bottom:6px;text-align:center;background:var(--ts-surface);
  transition:border-color .12s ease, background .12s ease;cursor:pointer;
  user-select:none;-webkit-user-select:none;}
.dl-card:hover{border-color:var(--ts-border-lit);}
[data-testid="stColumn"]:has(input:checked) .dl-card,
[data-testid="column"]:has(input:checked) .dl-card{
  border-color:var(--ts-cyan);background:rgba(37,244,238,.07);
  box-shadow:0 0 0 1px rgba(37,244,238,.35);}
[data-testid="stColumn"]:has(input:checked) .dl-card .dl-tick,
[data-testid="column"]:has(input:checked) .dl-card .dl-tick{opacity:1;}
.dl-tick{position:absolute;top:8px;right:8px;width:20px;height:20px;border-radius:50%;
  background:var(--ts-grad);color:#06080C;font-size:13px;font-weight:800;line-height:20px;
  opacity:0;transition:opacity .12s ease;}
.dl-thumb{width:100%;aspect-ratio:9/16;object-fit:cover;border-radius:8px;
  background:var(--ts-surface2);margin-bottom:6px;pointer-events:none;}
.dl-title{font-size:11.5px;font-weight:600;line-height:1.35;max-height:2.7em;
  overflow:hidden;margin-bottom:4px;}
.dl-meta{font-size:10.5px;color:var(--ts-muted);}
/* the per-card checkbox is driven by the card; keep it out of the way */
.dl-grid-scope [data-testid="stCheckbox"]{height:0;overflow:hidden;margin:0;padding:0;}
#dl-marquee{position:fixed;border:1.5px solid #25F4EE;background:rgba(37,244,238,.14);
  border-radius:4px;pointer-events:none;z-index:99999;display:none;}
.dl-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:4px 0 14px;
  padding:10px 14px;border:1px solid var(--ts-border);border-radius:12px;
  background:var(--ts-surface);}
.dl-bar button{background:var(--ts-surface2);color:var(--ts-text);border:1px solid var(--ts-border-lit);
  border-radius:9px;padding:5px 12px;font-size:.82rem;font-weight:600;cursor:pointer;
  font-family:inherit;transition:all .14s ease;}
.dl-bar button:hover{border-color:var(--ts-cyan);color:var(--ts-cyan);}
#dl-count{margin-left:auto;font-weight:700;font-size:.86rem;color:var(--ts-cyan);}
</style>
""", unsafe_allow_html=True)

        with st.form("dl_pick_form", border=False):
            st.markdown(
                '<div class="dl-grid-scope">'
                '<div class="dl-bar">'
                '  <button type="button" id="dl-all">Select all</button>'
                '  <button type="button" id="dl-none">Clear</button>'
                '  <button type="button" id="dl-invert">Invert</button>'
                '  <span id="dl-count">0 selected</span>'
                '</div></div>',
                unsafe_allow_html=True,
            )

            cols_per_row = 4
            for row_start in range(0, len(videos), cols_per_row):
                cols = st.columns(cols_per_row)
                for col, video in zip(cols, videos[row_start:row_start + cols_per_row]):
                    with col:
                        _thumb = (f'<img class="dl-thumb" src="{video["thumbnail"]}" loading="lazy">'
                                  if video.get("thumbnail") else '<div class="dl-thumb"></div>')
                        st.markdown(
                            f'<div class="dl-card">{_thumb}'
                            f'<div class="dl-tick">✓</div>'
                            f'<div class="dl-title">{video["title"][:70]}</div>'
                            f'<div class="dl-meta">👁️ {video["views"]} &nbsp; ❤️ {video["likes"]}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        st.checkbox("Select", key=f"dlpick_{video['id']}",
                                    label_visibility="collapsed")

            st.markdown("---")
            _f1, _f2 = st.columns([3, 1])
            with _f2:
                max_workers = st.slider(
                    "⚡ Parallel downloads", 1, 10, 5,
                    help="How many videos to download at the same time. 5 is a safe default — go "
                         "higher only if your connection is very fast and TikTok isn't rate-limiting you.",
                )
            with _f1:
                st.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
                dl_btn = st.form_submit_button(
                    "📥 Download selected as ZIP", type="primary", use_container_width=True,
                )

        # Client-side selection: card clicks, shift-ranges and marquee drag.
        # Everything here only toggles checkboxes that already exist, so if the
        # script fails the checkboxes still work on their own.
        components.html("""
<script>
(function(){
  const D = window.parent.document;
  if(!D) return;
  let anchor = null;

  const cells = () => {
    const scope = D.querySelector('[data-testid="stForm"]');
    if(!scope) return [];
    return [...scope.querySelectorAll('[data-testid="stCheckbox"] input[type=checkbox]')]
      .map(inp => ({inp, cell: inp.closest('[data-testid="stColumn"],[data-testid="column"]')}))
      .filter(x => x.cell && x.cell.querySelector('.dl-card'));
  };
  const setChecked = (inp, want) => { if(inp.checked !== want) inp.click(); };
  // React commits checkbox state on its own tick, so reading synchronously
  // right after a .click() returns the pre-click value. Always defer.
  const paint = () => {
    const c = cells(), n = c.filter(x => x.inp.checked).length;
    const el = D.getElementById('dl-count');
    if(el) el.textContent = n + ' / ' + c.length + ' selected';
  };
  const refresh = () => { setTimeout(paint, 0); setTimeout(paint, 120); };

  function wire(){
    const scope = D.querySelector('[data-testid="stForm"]');
    if(!scope || !D.querySelector('.dl-card')) return false;
    if(scope.dataset.dlWired === '1'){ refresh(); return true; }
    scope.dataset.dlWired = '1';

    const all = D.getElementById('dl-all'),
          none = D.getElementById('dl-none'),
          inv = D.getElementById('dl-invert');
    if(all)  all.onclick  = e => {e.preventDefault(); cells().forEach(x=>setChecked(x.inp,true));  refresh();};
    if(none) none.onclick = e => {e.preventDefault(); cells().forEach(x=>setChecked(x.inp,false)); refresh();};
    if(inv)  inv.onclick  = e => {e.preventDefault(); cells().forEach(x=>x.inp.click());           refresh();};

    let band = D.getElementById('dl-marquee');
    if(!band){ band = D.createElement('div'); band.id = 'dl-marquee'; D.body.appendChild(band); }

    let sx=0, sy=0, dragging=false, moved=false, additive=true;

    scope.addEventListener('mousedown', ev => {
      if(ev.button !== 0) return;
      if(ev.target.closest('button, input, .dl-bar, [data-testid="stSlider"]')) return;
      const c = cells(); if(!c.length) return;
      sx = ev.clientX; sy = ev.clientY;
      dragging = true; moved = false; additive = !ev.altKey;
      ev.preventDefault();
    });

    D.addEventListener('mousemove', ev => {
      if(!dragging) return;
      if(!moved && Math.hypot(ev.clientX-sx, ev.clientY-sy) < 5) return;
      moved = true;
      const x = Math.min(sx, ev.clientX), y = Math.min(sy, ev.clientY);
      const w = Math.abs(ev.clientX-sx), h = Math.abs(ev.clientY-sy);
      Object.assign(band.style, {display:'block', left:x+'px', top:y+'px',
                                 width:w+'px', height:h+'px'});
      cells().forEach(({cell}) => {
        const r = cell.getBoundingClientRect();
        const hit = !(r.right < x || r.left > x+w || r.bottom < y || r.top > y+h);
        const card = cell.querySelector('.dl-card');
        if(card) card.style.outline = hit ? '2px solid #FE2C55' : '';
      });
    });

    D.addEventListener('mouseup', ev => {
      if(!dragging) return;
      dragging = false;
      band.style.display = 'none';
      const c = cells();
      c.forEach(({cell}) => { const k = cell.querySelector('.dl-card'); if(k) k.style.outline=''; });

      if(moved){
        const x = Math.min(sx, ev.clientX), y = Math.min(sy, ev.clientY);
        const w = Math.abs(ev.clientX-sx), h = Math.abs(ev.clientY-sy);
        c.forEach(({inp, cell}) => {
          const r = cell.getBoundingClientRect();
          if(!(r.right < x || r.left > x+w || r.bottom < y || r.top > y+h)) setChecked(inp, additive);
        });
      } else {
        const cell = ev.target.closest('[data-testid="stColumn"],[data-testid="column"]');
        if(cell && cell.querySelector('.dl-card')){
          const idx = c.findIndex(z => z.cell === cell);
          if(idx >= 0){
            if(ev.shiftKey && anchor !== null){
              const [a,b] = [Math.min(anchor,idx), Math.max(anchor,idx)];
              for(let i=a;i<=b;i++) setChecked(c[i].inp, true);
            } else {
              c[idx].inp.click();
              anchor = idx;
            }
          }
        }
      }
      refresh();
    });

    scope.addEventListener('change', refresh, true);
    refresh();
    return true;
  }

  let tries = 0;
  const t = setInterval(() => { if(wire() || ++tries > 60) clearInterval(t); }, 150);
})();
</script>
""", height=0)

        if dl_btn:
            # Pass full video objects so downloader has the real URL
            st.session_state.dl_selected = {
                v["id"] for v in st.session_state.dl_videos
                if st.session_state.get(f"dlpick_{v['id']}")
            }
            selected_videos = [
                v for v in st.session_state.dl_videos
                if v["id"] in st.session_state.dl_selected
            ]
            if not selected_videos:
                st.warning("Nothing selected — tick at least one video first.")
                st.stop()
            # Create a persistent batch on disk — survives sleep / lost connection
            batch_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            batch_dir = os.path.join(DL_ROOT, batch_id)
            manifest = {
                "created": datetime.datetime.now().isoformat(),
                "videos": selected_videos,
                "workers": max_workers,
                "status": "in_progress",
            }
            dl_save_manifest(batch_dir, manifest)
            dl_execute_batch(batch_dir, manifest)


# ============================================================
# TAB 2 — Variant Generator (original Streamlit app)
# ============================================================
with tab2:
    st.header("🎛️ TikTok Variant Generator")
    st.markdown("Generate up to **5 variants** of your videos (120fps • 4000kbps • 1080×1920)")

    # ---- Constants ----
    TARGET_W, TARGET_H = 1080, 1920
    MAX_FPS = 120
    SAFE_THREADS = ["-threads", "2"]
    TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")

    # ---- Helpers ----
    def vg_run(cmd):
        try:
            return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, timeout=30)
        except Exception as e:
            st.error(f"run() error: {e}")
            return None

    def ffprobe_json(path, select="format"):
        try:
            p = vg_run([FFPROBE, "-v", "error", "-show_entries", select, "-of", "json", path])
            return json.loads(p.stdout) if p else {}
        except Exception as e:
            st.error(f"ffprobe_json error: {e}")
            return {}

    def ffprobe_streams(path):
        try:
            p = vg_run([FFPROBE, "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height,r_frame_rate,avg_frame_rate",
                        "-of", "json", path])
            return json.loads(p.stdout).get("streams", [{}])[0] if p else {}
        except Exception as e:
            st.error(f"ffprobe_streams error: {e}")
            return {}

    def parse_fps(rate_str):
        try:
            if not rate_str or rate_str == "0/0":
                return None
            n, d = rate_str.split("/")
            return float(n) / float(d) if float(d) else float(n)
        except Exception:
            return None

    def get_video_meta(path):
        try:
            s = ffprobe_streams(path)
            return s.get("width"), s.get("height"), parse_fps(
                s.get("avg_frame_rate") or s.get("r_frame_rate")
            )
        except Exception as e:
            st.error(f"get_video_meta error: {e}")
            return None, None, None

    def get_duration_seconds(path):
        try:
            data = ffprobe_json(path, select="format")
            dur = data.get("format", {}).get("duration")
            return float(dur) if dur else None
        except Exception:
            return None

    def parse_progress(line):
        try:
            m = TIME_RE.search(line or "")
            if not m:
                return None
            h, m_, s = m.groups()
            return int(h) * 3600 + int(m_) * 60 + float(s)
        except Exception:
            return None

    def run_ffmpeg_with_progress(cmd, total_seconds, progress_cb=None, log_cb=None):
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                    text=True, bufsize=1, errors="replace")
            start_time = time.time()
            last_progress_time = start_time
            timeout_seconds = 600

            for line in proc.stderr:
                if "time=" in line and log_cb:
                    log_cb(line.rstrip("\n"))
                t = parse_progress(line)
                if t is not None and total_seconds and progress_cb:
                    pct = max(0, min(100, int(t / total_seconds * 100)))
                    progress_cb(pct)
                    last_progress_time = time.time()

                if time.time() - last_progress_time > 120:
                    st.error("FFmpeg stuck (no progress 120s). Terminating.")
                    proc.terminate()
                    time.sleep(2)
                    if proc.poll() is None:
                        proc.kill()
                    return -2

                if time.time() - start_time > timeout_seconds:
                    st.error(f"FFmpeg timeout after {timeout_seconds}s. Terminating.")
                    proc.terminate()
                    time.sleep(2)
                    if proc.poll() is None:
                        proc.kill()
                    return -3

            rc = proc.wait()
            if progress_cb:
                progress_cb(100 if rc == 0 else 0)
            return rc
        except Exception as e:
            st.error(f"run_ffmpeg_with_progress error: {e}\n{traceback.format_exc()}")
            return -1

    def ffmpeg_prefix(use_hw):
        return [FFMPEG, "-y", "-hwaccel", "videotoolbox"] if use_hw else [FFMPEG, "-y"]

    def build_ffmpeg_cmd(
        input_path, out_path, *,
        variant_name, use_hw_decode, use_ultra_stable,
        hook_type, hook_dur, hook_img_path, hook_vid_path, hook_keep_audio,
        zoom_mode, audio_mode, add_blank_intro, blank_intro_sec, overlay_img_path=None,
    ):
        try:
            fps = 120
            br_k = 4000
            w, h, in_fps = get_video_meta(input_path)
            out_fps = min(fps, MAX_FPS)

            base_zoom = []
            if zoom_mode == "zoom + crop":
                base_zoom.append("scale=iw*1.01:ih*1.01,crop=iw:ih")
            elif zoom_mode == "zoom inverse + pad":
                base_zoom.append("scale=iw*0.99:ih*0.99,pad=iw:ih:(ow-iw)/2:(oh-ih)/2")

            if (w, h) == (TARGET_W, TARGET_H) and zoom_mode == "aucun":
                target_norm = f"format=yuv420p,fps={out_fps}"
            else:
                target_norm = (
                    f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
                    f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,fps={out_fps}"
                )
            base_vf = ",".join([*base_zoom, target_norm]) if base_zoom else target_norm

            metadata_clear = [
                "-map_metadata", "-1",
                "-metadata", f"title=Variant_{variant_name}",
                "-metadata", f"creation_time={datetime.datetime.now().isoformat()}",
            ]

            if use_ultra_stable:
                v_common = (["-b:v", f"{br_k}k", "-c:v", "libx264", "-preset", "veryfast",
                             "-pix_fmt", "yuv420p"] + SAFE_THREADS + metadata_clear)
            else:
                v_common = (["-b:v", f"{br_k}k", "-c:v", "h264_videotoolbox",
                             "-pix_fmt", "yuv420p"] + SAFE_THREADS + metadata_clear)

            def a_simple():
                if audio_mode == "pitch +1%":
                    return ["-filter:a", "asetrate=44100*1.01,aresample=44100", "-c:a", "aac"]
                elif audio_mode == "pitch -1%":
                    return ["-filter:a", "asetrate=44100*0.99,aresample=44100", "-c:a", "aac"]
                return ["-c:a", "aac", "-ar", "44100", "-ac", "2"]

            def a_complex(label_in):
                if audio_mode == "pitch +1%":
                    return f"{label_in}asetrate=44100*1.01,aresample=44100,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"
                if audio_mode == "pitch -1%":
                    return f"{label_in}asetrate=44100*0.99,aresample=44100,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"
                return f"{label_in}aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"

            a_out = ["-c:a", "aac", "-ar", "44100", "-ac", "2"]

            # Variant 5 overlay
            if variant_name == "5" and overlay_img_path:
                cmd = ffmpeg_prefix(use_hw_decode) + ["-i", input_path, "-i", overlay_img_path]
                fc = (f"[0:v]{base_vf}[base];"
                      f"[1:v]scale={TARGET_W}:{TARGET_H}[overlay];"
                      f"[base][overlay]overlay=0:0[vout];"
                      f"{a_complex('[0:a]')}[aout]")
                cmd += ["-filter_complex", fc, "-map", "[vout]", "-map", "[aout]"] + v_common + a_out + [out_path]
                return cmd, br_k, get_duration_seconds(input_path) or 0

            # No hook
            if hook_type == "None":
                if add_blank_intro and blank_intro_sec > 0:
                    cmd = ffmpeg_prefix(use_hw_decode) + [
                        "-f", "lavfi", "-t", f"{blank_intro_sec}",
                        "-i", f"color=size={TARGET_W}x{TARGET_H}:color=black:rate={out_fps},format=yuv420p",
                        "-f", "lavfi", "-t", f"{blank_intro_sec}",
                        "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                        "-i", input_path,
                        "-filter_complex",
                        f"[2:v]{base_vf}[vm];"
                        f"{a_complex('[2:a]')}[am];"
                        "[0:v][1:a][vm][am]concat=n=2:v=1:a=1[vout][aout]",
                        "-map", "[vout]", "-map", "[aout]",
                    ] + v_common + a_out + [out_path]
                    return cmd, br_k, (blank_intro_sec or 0) + (get_duration_seconds(input_path) or 0)
                else:
                    cmd = (ffmpeg_prefix(use_hw_decode)
                           + ["-i", input_path, "-vf", base_vf, "-r", str(out_fps),
                              "-map", "0:v:0", "-map", "0:a?"]
                           + v_common + a_simple() + [out_path])
                    return cmd, br_k, get_duration_seconds(input_path) or 0

            # Image overlay
            if hook_type == "Image overlay":
                cmd = ffmpeg_prefix(use_hw_decode) + ["-i", input_path, "-loop", "1", "-t", f"{hook_dur}", "-i", hook_img_path]
                fc = (f"[0:v]{base_vf}[base];"
                      f"[1:v][base]scale2ref=w=iw:h=ih[img][b2];"
                      f"[b2][img]overlay=(W-w)/2:(H-h)/2:enable='between(t,0,{hook_dur})'[vout];"
                      f"{a_complex('[0:a]')}[aout]")
                cmd += ["-filter_complex", fc, "-map", "[vout]", "-map", "[aout]"] + v_common + a_out + [out_path]
                return cmd, br_k, get_duration_seconds(input_path) or 0

            # Video prepend
            if hook_type == "Video prepend":
                cmd = ffmpeg_prefix(use_hw_decode) + ["-i", hook_vid_path, "-i", input_path]
                tnorm = (f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
                         f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,fps={out_fps}")
                fc = f"[0:v]{tnorm}[vh];[1:v]{base_vf}[vm];"
                if hook_keep_audio:
                    fc += f"{a_complex('[0:a]')}[ah];"
                else:
                    fc += "anullsrc=channel_layout=stereo:sample_rate=44100[ah];"
                fc += f"{a_complex('[1:a]')}[am];[vh][ah][vm][am]concat=n=2:v=1:a=1[vout][aout]"
                cmd += ["-filter_complex", fc, "-map", "[vout]", "-map", "[aout]"] + v_common + a_out + [out_path]
                return cmd, br_k, (get_duration_seconds(hook_vid_path) or 0) + (get_duration_seconds(input_path) or 0)

            # Video overlay
            if hook_type == "Video overlay":
                cmd = ffmpeg_prefix(use_hw_decode) + ["-i", input_path, "-i", hook_vid_path]
                tnorm = (f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
                         f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,fps={out_fps}")
                fc = (f"[0:v]{base_vf}[base];[1:v]{tnorm}[hv];"
                      f"[base][hv]overlay=(W-w)/2:(H-h)/2:enable='between(t,0,{hook_dur})'[vout];"
                      f"{a_complex('[0:a]')}[aout]")
                cmd += ["-filter_complex", fc, "-map", "[vout]", "-map", "[aout]"] + v_common + a_out + [out_path]
                return cmd, br_k, get_duration_seconds(input_path) or 0

            # Fallback
            cmd = (ffmpeg_prefix(use_hw_decode)
                   + ["-i", input_path, "-vf", base_vf, "-r", str(out_fps),
                      "-map", "0:v:0", "-map", "0:a?"]
                   + v_common + a_out + [out_path])
            return cmd, br_k, get_duration_seconds(input_path) or 0

        except Exception as e:
            st.error(f"build_ffmpeg_cmd error: {e}\n{traceback.format_exc()}")
            return None, None, None

    # ---- Sidebar-style options inside tab ----
    with st.expander("⚙️ Options", expanded=True):
        col_a, col_b = st.columns(2)
        with col_a:
            use_ultra_stable = st.checkbox("Mode ultra-stable (libx264/veryfast)", value=True)
            use_hw_decode = st.checkbox("Hardware decode (Videotoolbox)", value=False)
            zoom_mode = st.radio("Creative zoom mode", ["zoom + crop", "zoom inverse + pad", "aucun"], index=0)
        with col_b:
            selected_variants = st.multiselect(
                "Variants to generate",
                options=["1", "2", "3", "4", "5"],
                default=["1", "2", "3", "4"],
                help="1=Base | 2=+Intro+Hook | 3=+Pitch+1% | 4=+Pitch-1% | 5=Overlay",
            )
            hook_type = st.selectbox("Hook type (V2/V3/V4)", ["None", "Image overlay", "Video prepend", "Video overlay"])

    with st.expander("🎣 Hook & Overlay files"):
        hook_img = None
        hook_vid = None
        hook_keep_audio = False
        overlay_img = None

        if hook_type == "Image overlay":
            hook_img = st.file_uploader("Hook image (PNG/JPG)", type=["png", "jpg", "jpeg"], key="vg_hook_img")
        elif hook_type in ("Video prepend", "Video overlay"):
            hook_vid = st.file_uploader("Hook video (mp4/mov)", type=["mp4", "mov", "m4v"], key="vg_hook_vid")
            if hook_type == "Video prepend":
                hook_keep_audio = st.checkbox("Keep hook audio (prepend)", value=True)

        overlay_img = st.file_uploader("Variant 5 — Overlay/Border PNG (transparent)", type=["png"], key="vg_overlay")

    st.markdown("### 📥 Videos to process")
    videos = st.file_uploader(
        "Drop one or more videos",
        type=["mp4", "mov", "m4v"],
        accept_multiple_files=True,
        key="vg_videos",
    )

    st.markdown("---")
    run_btn = st.button("🚀 Generate Selected Variants", type="primary")

    if run_btn and videos:
        if not selected_variants:
            st.error("Select at least one variant.")
        else:
            try:
                all_variants_def = {
                    "1": {"name": "1", "hook_dur": 0.3, "add_intro": False, "intro_sec": 0.0, "audio": "normal"},
                    "2": {"name": "2", "hook_dur": 0.1, "add_intro": True,  "intro_sec": 0.01, "audio": "normal"},
                    "3": {"name": "3", "hook_dur": 0.1, "add_intro": True,  "intro_sec": 0.01, "audio": "pitch +1%"},
                    "4": {"name": "4", "hook_dur": 0.1, "add_intro": True,  "intro_sec": 0.01, "audio": "pitch -1%"},
                    "5": {"name": "5", "hook_dur": 0.3, "add_intro": False, "intro_sec": 0.0, "audio": "normal"},
                }
                variants = [all_variants_def[v] for v in selected_variants]
                total_tasks = len(videos) * len(variants)
                completed_tasks = 0
                overall_progress = st.progress(0)
                overall_status = st.empty()
                overall_status.markdown(f"### {len(videos)} video(s) × {len(variants)} variant(s) = **{total_tasks} tasks**")

                all_generated_files = []

                # Save hook/overlay files once
                hook_img_path = hook_vid_path = overlay_img_path = None
                if hook_type == "Image overlay" and hook_img:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(hook_img.name)[1]) as f:
                        f.write(hook_img.read())
                        hook_img_path = f.name
                if hook_type in ("Video prepend", "Video overlay") and hook_vid:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(hook_vid.name)[1]) as f:
                        f.write(hook_vid.read())
                        hook_vid_path = f.name
                if overlay_img:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
                        f.write(overlay_img.read())
                        overlay_img_path = f.name

                for video_idx, file in enumerate(videos):
                    st.markdown(f"---\n## 🎬 Video {video_idx+1}/{len(videos)}: **{file.name}**")
                    input_path = None
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as tmp:
                            tmp.write(file.read())
                            input_path = tmp.name
                    except Exception as e:
                        st.error(f"Failed to save input: {e}")
                        continue

                    base_name = os.path.splitext(os.path.basename(file.name))[0]

                    for variant_idx, variant in enumerate(variants):
                        try:
                            out_name = f"{base_name}_{variant['name']}.mp4"
                            out_tmp = os.path.join(tempfile.gettempdir(), out_name)
                            overall_status.markdown(
                                f"Video **{video_idx+1}/{len(videos)}** • "
                                f"Variant **{variant['name']}** • "
                                f"Progress: **{completed_tasks}/{total_tasks}**"
                            )
                            st.markdown(f"### ▶️ Variant {variant['name']}")
                            cmd, br, est_total = build_ffmpeg_cmd(
                                input_path, out_tmp,
                                variant_name=variant["name"],
                                use_hw_decode=use_hw_decode,
                                use_ultra_stable=use_ultra_stable,
                                hook_type=hook_type,
                                hook_dur=variant["hook_dur"],
                                hook_img_path=hook_img_path,
                                hook_vid_path=hook_vid_path,
                                hook_keep_audio=hook_keep_audio,
                                zoom_mode=zoom_mode,
                                audio_mode=variant["audio"],
                                add_blank_intro=variant["add_intro"],
                                blank_intro_sec=variant["intro_sec"],
                                overlay_img_path=overlay_img_path,
                            )
                            if cmd is None:
                                st.error(f"Failed to build command for variant {variant['name']}")
                                completed_tasks += 1
                                overall_progress.progress(completed_tasks / total_tasks)
                                continue

                            pbar = st.progress(0)
                            ptxt = st.empty()
                            log_exp = st.expander(f"FFmpeg logs — variant {variant['name']}", expanded=False)
                            log_box = log_exp.empty()

                            def prog_cb(p, _pb=pbar, _pt=ptxt):
                                _pb.progress(p)
                                _pt.markdown(f"Progress: **{p}%**")

                            def log_cb(line, _lb=log_box):
                                _lb.code(line, language="bash")

                            rc = run_ffmpeg_with_progress(cmd, est_total or 0, progress_cb=prog_cb, log_cb=log_cb)

                            if rc == 0:
                                st.success(f"✅ Variant {variant['name']} done → {out_name}")
                                all_generated_files.append({"path": out_tmp, "name": out_name})
                            else:
                                st.error(f"FFmpeg error code {rc} for variant {variant['name']}")

                            completed_tasks += 1
                            overall_progress.progress(completed_tasks / total_tasks)

                        except Exception as e:
                            st.error(f"Error on variant {variant['name']}: {e}\n{traceback.format_exc()}")
                            completed_tasks += 1
                            overall_progress.progress(completed_tasks / total_tasks)

                    if input_path:
                        try:
                            os.unlink(input_path)
                        except Exception:
                            pass

                # ---- Final ZIP download ----
                st.markdown("---\n# 📦 Done")
                if all_generated_files:
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                        for fi in all_generated_files:
                            try:
                                zf.write(fi["path"], fi["name"])
                            except Exception as e:
                                st.warning(f"Could not add {fi['name']}: {e}")
                    zip_buffer.seek(0)
                    zip_filename = f"TikTok_Variants_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.zip"
                    st.success(f"🎉 {len(all_generated_files)} variant(s) generated!")
                    st.balloons()
                    st.download_button(
                        label=f"⬇️ Download all variants ({len(all_generated_files)} files)",
                        data=zip_buffer,
                        file_name=zip_filename,
                        mime="application/zip",
                        key="vg_download_zip",
                    )
                    for fi in all_generated_files:
                        try:
                            os.unlink(fi["path"])
                        except Exception:
                            pass
                    for p in [hook_img_path, hook_vid_path, overlay_img_path]:
                        if p:
                            try:
                                os.unlink(p)
                            except Exception:
                                pass
                else:
                    st.error("No videos were successfully generated.")

            except Exception as e:
                st.error(f"FATAL: {e}\n{traceback.format_exc()}")

    elif not videos:
        st.info("Upload videos above, then click **Generate Selected Variants**.")
        st.markdown("""
**Variant guide:**
| # | Description |
|---|---|
| 1 | Base — 120fps, 4000kbps |
| 2 | + Invisible black intro (0.01s) + Hook (0.1s) |
| 3 | Variant 2 + Audio pitch +1% |
| 4 | Variant 2 + Audio pitch −1% |
| 5 | + Custom overlay/border PNG |
        """)


# ============================================================
# TAB 3 — Refresh Metadata (make re-uploads look "new")
# ============================================================
with tab3:
    st.header("🔄 Refresh Metadata")
    st.markdown(
        "Upload videos you already downloaded from TikTok and re-export them with "
        "**brand-new metadata + a unique digital fingerprint** — so they look fresh "
        "to the algorithm when you re-upload them."
    )

    # ---- Device / location pools ----------------------------------
    RM_DEVICE_PROFILES = [
        {"make": "Apple",   "model": "iPhone 15 Pro Max", "software": "17.4.1"},
        {"make": "Apple",   "model": "iPhone 15 Pro",     "software": "17.4"},
        {"make": "Apple",   "model": "iPhone 14 Pro Max", "software": "17.3.1"},
        {"make": "Apple",   "model": "iPhone 14",         "software": "17.2"},
        {"make": "Apple",   "model": "iPhone 13 Pro",     "software": "16.6.1"},
        {"make": "Apple",   "model": "iPhone 13",         "software": "16.5"},
        {"make": "samsung", "model": "SM-S928B",          "software": "Android 14"},
        {"make": "samsung", "model": "SM-S918B",          "software": "Android 14"},
        {"make": "samsung", "model": "SM-A546E",          "software": "Android 13"},
    ]

    # Default batch device = iPhone (matches "same iPhone, same country" request).
    # The re-roll button can still pick any profile, including Samsung.
    RM_IPHONE_PROFILES = [p for p in RM_DEVICE_PROFILES if p["make"] == "Apple"]

    # All locations across Saudi Arabia — picked per video so each one looks
    # like it was filmed in a different city, but always inside KSA.
    RM_SAUDI_LOCATIONS = [
        ("Riyadh",          24.7136, 46.6753),
        ("Jeddah",          21.4858, 39.1925),
        ("Mecca",           21.3891, 39.8579),
        ("Medina",          24.5247, 39.5692),
        ("Dammam",          26.4207, 50.0888),
        ("Khobar",          26.2172, 50.1971),
        ("Dhahran",         26.2361, 50.0393),
        ("Taif",            21.2703, 40.4158),
        ("Abha",            18.2164, 42.5053),
        ("Khamis Mushait",  18.3000, 42.7333),
        ("Tabuk",           28.3998, 36.5715),
        ("Hail",            27.5114, 41.7208),
        ("Buraidah",        26.3260, 43.9750),
        ("Unaizah",         26.0844, 43.9935),
        ("Najran",          17.4933, 44.1277),
        ("Jazan",           16.8892, 42.5611),
        ("Yanbu",           24.0895, 38.0618),
        ("Al Ahsa",         25.3833, 49.5856),
        ("Jubail",          27.0046, 49.6225),
        ("Qatif",           26.5196, 50.0078),
        ("Hafr Al-Batin",   28.4342, 45.9601),
        ("Al Kharj",        24.1556, 47.3350),
        ("Sakaka",          29.9697, 40.2064),
        ("Arar",            30.9753, 41.0381),
        ("Al Bahah",        20.0129, 41.4677),
    ]

    # Saudi Arabia Standard Time = UTC+3, no daylight saving
    RM_KSA_TZ = datetime.timedelta(hours=3)

    RM_INTENSITY = {
        "Light":  {"crop": (0.985, 0.995), "bright": (-0.012, 0.012), "contrast": (0.99, 1.01),
                   "sat": (0.98, 1.02),   "noise": (1, 2), "pitch": (0.997, 1.003)},
        "Medium": {"crop": (0.965, 0.985), "bright": (-0.02, 0.02),  "contrast": (0.97, 1.03),
                   "sat": (0.95, 1.05),   "noise": (2, 4), "pitch": (0.99, 1.01)},
        "Strong": {"crop": (0.94, 0.965),  "bright": (-0.035, 0.035), "contrast": (0.94, 1.06),
                   "sat": (0.90, 1.10),   "noise": (3, 6), "pitch": (0.98, 1.02)},
    }

    # ---- Helpers ----------------------------------------------------
    def rm_random_riyadh_datetime(days_ago_max=10):
        """Return (local_riyadh_dt, utc_dt) at a believable 'human' hour."""
        now_riyadh = datetime.datetime.utcnow() + RM_KSA_TZ
        days_ago = random.randint(0, days_ago_max)
        base_date = (now_riyadh - datetime.timedelta(days=days_ago)).date()
        # Realistic posting hours: late morning to midnight
        hour   = random.randint(8, 23)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        local_dt = datetime.datetime.combine(
            base_date, datetime.time(hour, minute, second)
        )
        utc_dt = local_dt - RM_KSA_TZ
        return local_dt, utc_dt

    def rm_random_metadata_args(device_profile, city_name, lat, lon, days_ago_max=10):
        lat += random.uniform(-0.04, 0.04)
        lon += random.uniform(-0.04, 0.04)

        local_dt, utc_dt = rm_random_riyadh_datetime(days_ago_max)
        creation_time = utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000000Z")
        qt_creation   = local_dt.strftime("%Y-%m-%dT%H:%M:%S+0300")
        iso6709 = f"{lat:+.4f}{lon:+.4f}+000.000/"
        unique_id = uuid.uuid4().hex

        args = [
            "-map_metadata", "-1",
            "-map_chapters", "-1",
            "-metadata", f"creation_time={creation_time}",
            "-metadata", f"com.apple.quicktime.make={device_profile['make']}",
            "-metadata", f"com.apple.quicktime.model={device_profile['model']}",
            "-metadata", f"com.apple.quicktime.software={device_profile['software']}",
            "-metadata", f"com.apple.quicktime.creationdate={qt_creation}",
            "-metadata", f"com.apple.quicktime.location.ISO6709={iso6709}",
            "-metadata", "com.apple.quicktime.location.accuracy.horizontal=5.000000",
            "-metadata", f"com.apple.quicktime.content.identifier={unique_id}",
            "-metadata", f"encoder=HW_{unique_id[:10]}",
            "-metadata", "title=",
            "-metadata", "comment=",
            "-metadata", "description=",
        ]
        info = {
            "device": f"{device_profile['make']} {device_profile['model']}",
            "software": device_profile["software"],
            "location": f"{city_name}, Saudi Arabia",
            "date": local_dt.strftime("%Y-%m-%d %H:%M") + " (KSA time)",
            "id": unique_id[:12],
        }
        return args, info

    def rm_build_visual_filter(intensity):
        r = RM_INTENSITY[intensity]
        crop = random.uniform(*r["crop"])
        vf = (
            f"crop=iw*{crop:.4f}:ih*{crop:.4f},"
            f"scale=trunc(iw/{crop:.4f}/2)*2:trunc(ih/{crop:.4f}/2)*2"
        )
        bright   = random.uniform(*r["bright"])
        contrast = random.uniform(*r["contrast"])
        sat      = random.uniform(*r["sat"])
        vf += f",eq=brightness={bright:.4f}:contrast={contrast:.4f}:saturation={sat:.4f}"
        noise = random.randint(*r["noise"])
        vf += f",noise=alls={noise}:allf=t+u"
        return vf

    def rm_build_audio_filter(intensity):
        r = RM_INTENSITY[intensity]
        pitch = random.uniform(*r["pitch"])
        return f"asetrate=44100*{pitch:.5f},aresample=44100,atempo={1/pitch:.5f}"

    def rm_random_filename(ext="mp4"):
        ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        rid = uuid.uuid4().hex[:8].upper()
        return f"VID_{ts}_{rid}.{ext}"

    def rm_build_cmd(input_path, output_path, intensity, do_visual, do_audio, target_bitrate_k,
                     device_profile, city_name, lat, lon, days_ago_max=10):
        cmd = [FFMPEG, "-y", "-i", input_path]

        if do_visual:
            cmd += ["-vf", rm_build_visual_filter(intensity)]
        if do_audio:
            cmd += ["-af", rm_build_audio_filter(intensity)]

        meta_args, meta_info = rm_random_metadata_args(device_profile, city_name, lat, lon, days_ago_max)
        cmd += meta_args

        cmd += [
            "-c:v", "libx264", "-preset", "veryfast",
            "-b:v", f"{target_bitrate_k}k",
            "-maxrate", f"{int(target_bitrate_k*1.15)}k",
            "-bufsize", f"{int(target_bitrate_k*2)}k",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path,
        ]
        return cmd, meta_info

    # ---- UI -----------------------------------------------------------
    st.subheader("Step 1 — Upload Videos")
    rm_files = st.file_uploader(
        "Upload one or more videos (already downloaded from TikTok)",
        type=["mp4", "mov", "avi", "mkv", "webm"],
        accept_multiple_files=True,
        key="rm_files",
    )

    # ---- One consistent device for the whole batch -----------------
    if "rm_device" not in st.session_state:
        st.session_state.rm_device = random.choice(RM_IPHONE_PROFILES)

    rm_dev_col1, rm_dev_col2 = st.columns([4, 1])
    with rm_dev_col1:
        _dev = st.session_state.rm_device
        st.markdown(
            f"📱 **Device for this entire batch:** {_dev['make']} {_dev['model']} "
            f"(`{_dev['software']}`) — every refreshed video will look like it came "
            f"from this same phone."
        )
    with rm_dev_col2:
        if st.button("🔁 Re-roll device", use_container_width=True):
            st.session_state.rm_device = random.choice(RM_DEVICE_PROFILES)
            st.rerun()

    st.subheader("Step 2 — Refresh Options")
    rm_col1, rm_col2, rm_col3 = st.columns(3)
    with rm_col1:
        rm_intensity = st.select_slider(
            "Visual change intensity",
            options=["Light", "Medium", "Strong"],
            value="Medium",
            help="Higher = bigger crop/zoom, color shift & noise → stronger fingerprint change, "
                 "but slightly more visible to viewers.",
        )
    with rm_col2:
        rm_do_visual = st.checkbox("Apply visual micro-changes (crop/zoom/color/noise)", value=True)
        rm_do_audio  = st.checkbox("Apply audio pitch micro-shift", value=True)
    with rm_col3:
        rm_bitrate = st.slider("Output bitrate (kbps)", 2000, 6000, 4000, step=250)

    st.info(
        "ℹ️ Each video gets: **stripped original metadata** → **same device** "
        "(picked above) → **a different Saudi Arabia city/GPS location & a "
        "realistic Riyadh-time (UTC+3) creation date** → **unique content ID** → "
        "**new random filename**. With visual/audio changes enabled, the video's "
        "digital fingerprint also changes. All videos look like they came from the "
        "same iPhone/phone, just filmed in different cities across Saudi Arabia."
    )

    st.subheader("Step 3 — Refresh")
    rm_go = st.button("🔄 Refresh Metadata for All Videos", use_container_width=True,
                       disabled=not rm_files)

    if rm_go and rm_files:
        rm_results = []
        overall = st.progress(0)
        overall_txt = st.empty()
        total = len(rm_files)

        # Shuffle Saudi cities so consecutive videos don't repeat locations;
        # if there are more videos than cities, cycle through again.
        rm_city_pool = RM_SAUDI_LOCATIONS.copy()
        random.shuffle(rm_city_pool)
        rm_device = st.session_state.rm_device

        for idx, rm_file in enumerate(rm_files):
            overall_txt.markdown(f"Processing **{idx+1}/{total}** — `{rm_file.name}`")

            in_path = os.path.join(tempfile.gettempdir(), f"rm_in_{uuid.uuid4().hex[:8]}_{rm_file.name}")
            with open(in_path, "wb") as f:
                f.write(rm_file.getbuffer())

            out_name = rm_random_filename(ext="mp4")
            out_path = os.path.join(tempfile.gettempdir(), out_name)

            try:
                city_name, city_lat, city_lon = rm_city_pool[idx % len(rm_city_pool)]
                # Spread videos across the last ~10 days so timestamps look natural
                days_ago_max = max(1, min(10, total))
                cmd, meta_info = rm_build_cmd(
                    in_path, out_path, rm_intensity, rm_do_visual, rm_do_audio, rm_bitrate,
                    rm_device, city_name, city_lat, city_lon, days_ago_max
                )

                dur = get_duration_seconds(in_path) or 0

                pbar = st.progress(0)
                ptxt = st.empty()
                log_exp = st.expander(f"FFmpeg logs — {rm_file.name}", expanded=False)
                log_box = log_exp.empty()

                def prog_cb(p, _pb=pbar, _pt=ptxt):
                    _pb.progress(p)
                    _pt.markdown(f"Progress: **{p}%**")

                def log_cb(line, _lb=log_box):
                    _lb.code(line, language="bash")

                rc = run_ffmpeg_with_progress(cmd, dur, progress_cb=prog_cb, log_cb=log_cb)

                if rc == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    st.success(f"✅ `{rm_file.name}` → `{out_name}`")
                    st.markdown(
                        f"&nbsp;&nbsp;📱 **{meta_info['device']}** ({meta_info['software']}) "
                        f"• 📍 {meta_info['location']} • 🗓️ {meta_info['date']} "
                        f"• 🆔 `{meta_info['id']}`"
                    )
                    rm_results.append({"path": out_path, "name": out_name})
                else:
                    st.error(f"❌ FFmpeg error (code {rc}) for `{rm_file.name}`")

            except Exception as e:
                st.error(f"Error processing `{rm_file.name}`: {e}\n{traceback.format_exc()}")
            finally:
                try:
                    os.unlink(in_path)
                except Exception:
                    pass

            overall.progress((idx + 1) / total)

        # ---- ZIP download ----
        st.markdown("---")
        if rm_results:
            zip_buf = BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for r in rm_results:
                    try:
                        zf.write(r["path"], r["name"])
                    except Exception as e:
                        st.warning(f"Could not add {r['name']}: {e}")
            zip_buf.seek(0)

            st.success(f"🎉 {len(rm_results)}/{total} video(s) refreshed and ready!")
            st.balloons()
            st.download_button(
                label=f"⬇️ Download Refreshed Videos ({len(rm_results)} files)",
                data=zip_buf,
                file_name=f"Refreshed_Videos_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                mime="application/zip",
                key="rm_download_zip",
            )

            for r in rm_results:
                try:
                    os.unlink(r["path"])
                except Exception:
                    pass
        else:
            st.error("No videos were successfully refreshed.")

    elif not rm_files:
        st.info("Upload one or more videos above, then click **Refresh Metadata for All Videos**.")
        st.markdown("""
**What gets changed:**
| Item | Change |
|---|---|
| File name | Randomized (`VID_<timestamp>_<id>.mp4`) |
| Device make/model | **One iPhone for the whole batch** (re-rollable above) |
| GPS location | A different city across **Saudi Arabia** for each video |
| Creation date/time | Realistic Riyadh time (UTC+3), human posting hours, spread over recent days |
| Content ID | New random unique identifier |
| Visual (optional) | Subtle crop/zoom + color + noise |
| Audio (optional) | Subtle pitch micro-shift |

All original metadata (old device info, old GPS, old timestamps) is **stripped** before the new values are written. Using one consistent device with only the location/time changing per clip mimics how a real person posts multiple videos from the same phone while traveling around the country.
        """)


# ============================================================
# TAB 4 — Find Similar (visual search on TikTok only)
# ============================================================
with tab4:
    st.header("🔍 Find Similar Videos on TikTok")
    st.markdown(
        "Upload an image (screenshot, frame, photo) and find **visually similar "
        "TikTok videos**. Uses Google Lens filtered to TikTok content only."
    )

    # ---- API key setup -----------------------------------------------
    st.subheader("Step 1 — SerpAPI Key")
    st.markdown(
        "This feature uses [SerpAPI](https://serpapi.com/) to run a Google Lens "
        "visual search. **Free tier = 100 searches/month** — no credit card needed."
    )

    _fs_cfg_key, _fs_src = cfg_api_key("serpapi_key", "SERPAPI_KEY")
    if "serpapi_key" not in st.session_state:
        st.session_state.serpapi_key = ""

    if _fs_cfg_key:
        st.session_state.serpapi_key = _fs_cfg_key
        st.success(f"🔑 Key already configured (from the {_fs_src}) — nothing to do here.")
    else:
        fs_key = st.text_input(
            "SerpAPI Key",
            value=st.session_state.serpapi_key,
            type="password",
            help="Get your free key at https://serpapi.com/manage-api-key",
            key="fs_serpapi_input",
        )
        if fs_key:
            st.session_state.serpapi_key = fs_key

    # ---- Image upload ------------------------------------------------
    st.subheader("Step 2 — Upload Image")
    fs_image = st.file_uploader(
        "Upload the image you want to find similar TikTok videos for",
        type=["png", "jpg", "jpeg", "webp", "bmp"],
        key="fs_image",
    )

    if fs_image:
        st.image(fs_image, caption="Your image", width=300)

    # ---- Search ------------------------------------------------------
    st.subheader("Step 3 — Search")
    fs_go = st.button(
        "🔍 Find Similar on TikTok",
        use_container_width=True,
        disabled=not (fs_image and st.session_state.serpapi_key),
    )

    def fs_upload_temp_image(image_bytes, filename):
        """Upload image to a free temporary host and return a public URL."""
        try:
            resp = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": (filename, image_bytes)},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                url = data.get("data", {}).get("url", "")
                if url:
                    # tmpfiles.org returns viewer URL; convert to direct URL
                    return url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
        except Exception:
            pass

        # Fallback: file.io
        try:
            resp = requests.post(
                "https://file.io",
                files={"file": (filename, image_bytes)},
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json().get("link", "")
        except Exception:
            pass
        return ""

    def fs_google_lens_search(image_url, api_key):
        """Run Google Lens search via SerpAPI, return TikTok-only results."""
        params = {
            "engine": "google_lens",
            "url": image_url,
            "api_key": api_key,
        }
        resp = requests.get("https://serpapi.com/search.json", params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        tiktok_results = []

        # Check visual_matches
        for match in data.get("visual_matches", []):
            link = match.get("link", "")
            if "tiktok.com" in link:
                tiktok_results.append({
                    "title": match.get("title", "TikTok Video"),
                    "link": link,
                    "thumbnail": match.get("thumbnail", ""),
                    "source": match.get("source", "TikTok"),
                    "snippet": match.get("snippet", ""),
                })

        # Check knowledge_graph
        for item in data.get("knowledge_graph", []):
            for link_info in item.get("images", []):
                link = link_info.get("link", "")
                if "tiktok.com" in link:
                    tiktok_results.append({
                        "title": item.get("title", "TikTok Video"),
                        "link": link,
                        "thumbnail": link_info.get("thumbnail", ""),
                        "source": "TikTok",
                        "snippet": "",
                    })

        # Check reverse_image_search results via text_results
        for item in data.get("text_results", []):
            link = item.get("link", "")
            if "tiktok.com" in link:
                tiktok_results.append({
                    "title": item.get("title", "TikTok Video"),
                    "link": link,
                    "thumbnail": item.get("thumbnail", ""),
                    "source": "TikTok",
                    "snippet": item.get("snippet", ""),
                })

        # Deduplicate by link
        seen = set()
        unique = []
        for r in tiktok_results:
            if r["link"] not in seen:
                seen.add(r["link"])
                unique.append(r)
        return unique, data

    if fs_go and fs_image and st.session_state.serpapi_key:
        with st.spinner("Uploading image for visual search..."):
            image_bytes = fs_image.getvalue()
            image_url = fs_upload_temp_image(image_bytes, fs_image.name)

        if not image_url:
            st.error("Failed to upload image to temporary host. Please try again.")
        else:
            with st.spinner("Searching Google Lens for similar TikTok content..."):
                try:
                    results, raw_data = fs_google_lens_search(
                        image_url, st.session_state.serpapi_key
                    )
                except requests.exceptions.HTTPError as e:
                    st.error(f"SerpAPI error: {e}")
                    results = []
                    raw_data = {}
                except Exception as e:
                    st.error(f"Search failed: {e}")
                    results = []
                    raw_data = {}

            if results:
                st.success(f"Found **{len(results)}** similar TikTok video(s)!")
                st.markdown("---")

                for i, r in enumerate(results):
                    col_thumb, col_info = st.columns([1, 3])
                    with col_thumb:
                        if r["thumbnail"]:
                            try:
                                st.image(r["thumbnail"], width=150)
                            except Exception:
                                st.markdown("🎬")
                        else:
                            st.markdown("🎬")
                    with col_info:
                        st.markdown(f"**{r['title']}**")
                        if r["snippet"]:
                            st.caption(r["snippet"])
                        st.markdown(f"[🔗 Open on TikTok]({r['link']})")

                        # Extract video ID for download
                        vid_match = re.search(r"/video/(\d+)", r["link"])
                        if vid_match:
                            vid_id = vid_match.group(1)
                            dl_key = f"fs_dl_{i}_{vid_id}"
                            if st.button(f"⬇️ Download", key=dl_key):
                                with st.spinner(f"Downloading {vid_id}..."):
                                    dl_dir = tempfile.mkdtemp()
                                    dl_out = os.path.join(dl_dir, f"{vid_id}.%(ext)s")
                                    dl_cmd = [
                                        YTDLP, "-f", "bestvideo+bestaudio/best",
                                        "--merge-output-format", "mp4",
                                        "--no-warnings", "--no-check-certificate",
                                        "--retries", "5",
                                        "-o", dl_out, r["link"],
                                    ]
                                    dl_result = subprocess.run(
                                        dl_cmd, capture_output=True, timeout=240
                                    )
                                    if dl_result.returncode == 0:
                                        for fname in os.listdir(dl_dir):
                                            if fname.startswith(vid_id):
                                                fpath = os.path.join(dl_dir, fname)
                                                with open(fpath, "rb") as vf:
                                                    st.download_button(
                                                        "💾 Save Video",
                                                        data=vf.read(),
                                                        file_name=fname,
                                                        mime="video/mp4",
                                                        key=f"fs_save_{i}_{vid_id}",
                                                    )
                                                break
                                    else:
                                        st.warning("Download failed — video may be private or region-locked.")
                    st.markdown("---")

                # Download all button
                if len(results) > 1:
                    all_vid_links = [
                        r["link"] for r in results
                        if re.search(r"/video/(\d+)", r["link"])
                    ]
                    if all_vid_links and st.button(
                        f"⬇️ Download All {len(all_vid_links)} Videos",
                        use_container_width=True,
                        key="fs_dl_all",
                    ):
                        dl_dir = tempfile.mkdtemp()
                        dl_progress = st.progress(0)
                        dl_status = st.empty()
                        downloaded_files = []
                        for j, link in enumerate(all_vid_links):
                            vid_match = re.search(r"/video/(\d+)", link)
                            vid_id = vid_match.group(1) if vid_match else f"video_{j}"
                            dl_status.markdown(f"Downloading **{j+1}/{len(all_vid_links)}**...")
                            dl_out = os.path.join(dl_dir, f"{vid_id}.%(ext)s")
                            dl_cmd = [
                                YTDLP, "-f", "bestvideo+bestaudio/best",
                                "--merge-output-format", "mp4",
                                "--no-warnings", "--no-check-certificate",
                                "--retries", "5", "--sleep-requests", "1",
                                "-o", dl_out, link,
                            ]
                            try:
                                dl_result = subprocess.run(
                                    dl_cmd, capture_output=True, timeout=240
                                )
                                if dl_result.returncode == 0:
                                    for fname in os.listdir(dl_dir):
                                        if fname.startswith(vid_id):
                                            downloaded_files.append(
                                                os.path.join(dl_dir, fname)
                                            )
                                            break
                            except Exception:
                                pass
                            dl_progress.progress((j + 1) / len(all_vid_links))
                            time.sleep(1)

                        if downloaded_files:
                            zip_buf = BytesIO()
                            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                                for fp in downloaded_files:
                                    zf.write(fp, os.path.basename(fp))
                            zip_buf.seek(0)
                            st.download_button(
                                f"💾 Download ZIP ({len(downloaded_files)} videos)",
                                data=zip_buf,
                                file_name=f"Similar_TikTok_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                                mime="application/zip",
                                key="fs_dl_all_zip",
                            )
                        else:
                            st.error("No videos could be downloaded.")

            else:
                st.warning("No similar TikTok videos found for this image.")
                # Show what was found in general (non-TikTok) for context
                all_matches = raw_data.get("visual_matches", [])
                if all_matches:
                    with st.expander(f"Google Lens found {len(all_matches)} results on other sites"):
                        for m in all_matches[:10]:
                            st.markdown(f"- [{m.get('title', 'Result')}]({m.get('link', '#')}) — {m.get('source', '')}")
                st.info(
                    "💡 **Tip:** Try a clearer or more unique image. Screenshots of the "
                    "actual TikTok video frame work best."
                )

    elif not fs_image:
        st.info("Upload an image above to find similar TikTok videos.")
        st.markdown("""
**How it works:**
1. You provide your **SerpAPI key** (free at [serpapi.com](https://serpapi.com/))
2. Upload a screenshot or image frame
3. Google Lens does a **visual search** and we filter results to **TikTok only**
4. You can preview and download any matching videos directly

**Best results with:**
- Clear screenshots of actual TikTok video frames
- Product images, faces, or distinctive scenes
- Images with unique visual elements (not generic landscapes)
        """)


# ============================================================
# TAB 5 — Extract Audio from Videos
# ============================================================
with tab5:
    st.header("🎵 Extract Audio from Videos")
    st.markdown("Upload one or more videos and get their audio tracks — as MP3, WAV, or original quality M4A.")

    # ---- Options ----
    st.subheader("Step 1 — Upload Videos")
    ea_files = st.file_uploader(
        "Drop one or more videos",
        type=["mp4", "mov", "m4v", "avi", "mkv", "webm"],
        accept_multiple_files=True,
        key="ea_files",
    )

    st.subheader("Step 2 — Audio Options")
    ea_col1, ea_col2 = st.columns(2)
    with ea_col1:
        ea_format = st.selectbox(
            "Output format",
            ["MP3 (universal)", "M4A (fast — original quality)", "WAV (uncompressed)"],
            help="MP3 works everywhere. M4A copies the original audio without re-encoding (fastest, best quality). WAV is huge but lossless.",
        )
    with ea_col2:
        ea_bitrate = st.select_slider(
            "MP3 bitrate (kbps)",
            options=[128, 160, 192, 256, 320],
            value=192,
            disabled=not ea_format.startswith("MP3"),
        )

    def ea_build_cmd(in_path, out_path):
        base = [FFMPEG, "-y", "-i", in_path, "-vn"]
        if ea_format.startswith("MP3"):
            return base + ["-c:a", "libmp3lame", "-b:a", f"{ea_bitrate}k", out_path]
        if ea_format.startswith("M4A"):
            return base + ["-c:a", "copy", out_path]
        return base + ["-c:a", "pcm_s16le", "-ar", "44100", out_path]

    def ea_extract_one(in_path, out_path):
        """Extract audio. For M4A, fall back to AAC re-encode if stream copy fails
        (e.g. source audio isn't AAC)."""
        try:
            r = subprocess.run(ea_build_cmd(in_path, out_path), capture_output=True, timeout=300)
        except subprocess.TimeoutExpired:
            return False, "timed out after 300s"
        if r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return True, None
        if ea_format.startswith("M4A"):
            cmd = [FFMPEG, "-y", "-i", in_path, "-vn", "-c:a", "aac", "-b:a", "192k", out_path]
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=300)
            except subprocess.TimeoutExpired:
                return False, "timed out after 300s"
            if r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return True, None
        err = r.stderr.decode(errors="replace")[-300:] if r.stderr else "unknown error"
        return False, err

    st.subheader("Step 3 — Extract")
    ea_go = st.button(
        f"🎵 Extract Audio from {len(ea_files) if ea_files else 0} Video(s)",
        use_container_width=True,
        disabled=not ea_files,
    )

    if ea_go and ea_files:
        ea_ext = "mp3" if ea_format.startswith("MP3") else ("m4a" if ea_format.startswith("M4A") else "wav")
        ea_results = []
        ea_failed = []
        ea_progress = st.progress(0)
        ea_status = st.empty()
        total = len(ea_files)

        with tempfile.TemporaryDirectory() as ea_tmpdir:
            for idx, ea_file in enumerate(ea_files):
                ea_status.markdown(f"🎵 Extracting **{idx+1}/{total}** — `{ea_file.name}`")

                in_path = os.path.join(ea_tmpdir, f"in_{idx}_{ea_file.name}")
                with open(in_path, "wb") as f:
                    f.write(ea_file.getbuffer())

                base_name = os.path.splitext(os.path.basename(ea_file.name))[0]
                out_path = os.path.join(ea_tmpdir, f"{base_name}.{ea_ext}")

                ok, err = ea_extract_one(in_path, out_path)
                if ok:
                    with open(out_path, "rb") as f:
                        ea_results.append({"name": f"{base_name}.{ea_ext}", "data": f.read()})
                else:
                    ea_failed.append((ea_file.name, err))

                try:
                    os.unlink(in_path)
                except Exception:
                    pass
                ea_progress.progress((idx + 1) / total)

        if ea_results:
            if ea_failed:
                ea_status.warning(f"⚠️ {len(ea_results)}/{total} extracted — {len(ea_failed)} failed.")
            else:
                ea_status.success(f"✅ All {len(ea_results)} audio file(s) extracted!")

            if len(ea_results) == 1:
                st.download_button(
                    label=f"⬇️ Download {ea_results[0]['name']}",
                    data=ea_results[0]["data"],
                    file_name=ea_results[0]["name"],
                    mime="audio/mpeg" if ea_ext == "mp3" else ("audio/mp4" if ea_ext == "m4a" else "audio/wav"),
                    key="ea_dl_single",
                    use_container_width=True,
                )
            else:
                ea_zip = BytesIO()
                with zipfile.ZipFile(ea_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                    for r in ea_results:
                        zf.writestr(r["name"], r["data"])
                ea_zip.seek(0)
                st.download_button(
                    label=f"⬇️ Download ZIP ({len(ea_results)} audio files)",
                    data=ea_zip,
                    file_name=f"audio_extracted_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip",
                    key="ea_dl_zip",
                    use_container_width=True,
                )

            if ea_failed:
                with st.expander(f"⚠️ {len(ea_failed)} file(s) failed — details"):
                    for fname, err in ea_failed:
                        st.markdown(f"**{fname}**: {err}")
        else:
            ea_status.error("No audio could be extracted.")
            if ea_failed:
                with st.expander("Error details"):
                    for fname, err in ea_failed:
                        st.markdown(f"**{fname}**: {err}")

    elif not ea_files:
        st.info("Upload videos above, then click **Extract Audio**.")
        st.markdown("""
**Format guide:**
| Format | Best for | Speed | Size |
|---|---|---|---|
| MP3 | Sharing, editing apps, everywhere | Fast | Small |
| M4A | Keeping original TikTok audio quality (no re-encode) | Fastest | Small |
| WAV | Audio editing / production | Fast | Very large |
        """)


# ============================================================
# TAB 6 — Extract Text (speech-to-text transcription)
# ============================================================
with tab6:
    st.header("📝 Extract Text from Videos")
    st.markdown(
        "Transcribe the speech in your videos to text — **Arabic** or **English** — "
        "then copy it directly or download it as a `.txt` file. "
        "Runs 100% locally, no API key needed."
    )

    try:
        from faster_whisper import WhisperModel
        _fw_ok = True
    except ImportError:
        _fw_ok = False

    if not _fw_ok:
        st.error("The transcription engine isn't installed yet. Run this in Terminal, then restart the app:")
        st.code("pip install faster-whisper", language="bash")
    else:
        @st.cache_resource(show_spinner=False)
        def et_load_model(size):
            return WhisperModel(size, device="cpu", compute_type="int8")

        st.subheader("Step 1 — Upload Videos / Audio")
        et_files = st.file_uploader(
            "Drop one or more video or audio files",
            type=["mp4", "mov", "m4v", "avi", "mkv", "webm", "mp3", "m4a", "wav"],
            accept_multiple_files=True,
            key="et_files",
        )

        st.subheader("Step 2 — Options")
        et_col1, et_col2 = st.columns(2)
        with et_col1:
            et_lang_choice = st.selectbox(
                "Language",
                ["Auto-detect", "Arabic (العربية)", "English"],
                help="Pick the spoken language for best accuracy, or let it auto-detect.",
            )
        with et_col2:
            et_model_size = st.select_slider(
                "Accuracy vs speed",
                options=["base", "small", "medium"],
                value="small",
                help="base = fastest, medium = most accurate (especially for Arabic). "
                     "First use of a size downloads the model once (~150 MB–1.5 GB).",
            )

        ET_LANG_CODES = {"Auto-detect": None, "Arabic (العربية)": "ar", "English": "en"}

        st.subheader("Step 3 — Extract Text")
        et_go = st.button(
            f"📝 Extract Text from {len(et_files) if et_files else 0} File(s)",
            use_container_width=True,
            disabled=not et_files,
        )

        if "et_results" not in st.session_state:
            st.session_state.et_results = []

        if et_go and et_files:
            st.session_state.et_results = []
            et_progress = st.progress(0)
            et_status = st.empty()
            total = len(et_files)

            with et_status, st.spinner(f"Loading `{et_model_size}` model (first time downloads it)..."):
                et_model = et_load_model(et_model_size)

            with tempfile.TemporaryDirectory() as et_tmpdir:
                for idx, et_file in enumerate(et_files):
                    et_status.markdown(f"📝 Transcribing **{idx+1}/{total}** — `{et_file.name}`")

                    in_path = os.path.join(et_tmpdir, f"in_{idx}_{et_file.name}")
                    with open(in_path, "wb") as f:
                        f.write(et_file.getbuffer())

                    # Convert to 16 kHz mono WAV — what Whisper expects
                    wav_path = os.path.join(et_tmpdir, f"audio_{idx}.wav")
                    conv = subprocess.run(
                        [FFMPEG, "-y", "-i", in_path, "-vn",
                         "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path],
                        capture_output=True, timeout=300,
                    )
                    if conv.returncode != 0 or not os.path.exists(wav_path):
                        err = conv.stderr.decode(errors="replace")[-200:] if conv.stderr else "no audio track?"
                        st.session_state.et_results.append(
                            {"name": et_file.name, "text": "", "lang": "", "error": err}
                        )
                        et_progress.progress((idx + 1) / total)
                        continue

                    try:
                        segments, info = et_model.transcribe(
                            wav_path,
                            language=ET_LANG_CODES[et_lang_choice],
                            vad_filter=True,
                        )
                        text = "\n".join(s.text.strip() for s in segments).strip()
                        st.session_state.et_results.append({
                            "name": et_file.name,
                            "text": text or "(no speech detected)",
                            "lang": info.language,
                            "error": None,
                        })
                    except Exception as e:
                        st.session_state.et_results.append(
                            {"name": et_file.name, "text": "", "lang": "", "error": str(e)}
                        )

                    try:
                        os.unlink(in_path)
                        os.unlink(wav_path)
                    except Exception:
                        pass
                    et_progress.progress((idx + 1) / total)

            ok_count = sum(1 for r in st.session_state.et_results if not r["error"])
            if ok_count:
                et_status.success(f"✅ {ok_count}/{total} file(s) transcribed!")
            else:
                et_status.error("No files could be transcribed.")

        # ---- Results (persist across reruns so copy/download always work) ----
        if st.session_state.et_results:
            st.markdown("---")
            st.subheader("Results")
            ET_LANG_NAMES = {"ar": "Arabic", "en": "English"}

            for i, r in enumerate(st.session_state.et_results):
                if r["error"]:
                    st.error(f"❌ **{r['name']}** — {r['error']}")
                    continue

                lang_name = ET_LANG_NAMES.get(r["lang"], r["lang"])
                st.markdown(f"#### 🎬 {r['name']}  \n_Detected language: **{lang_name}**_")
                st.text_area(
                    "Transcription (click inside → Cmd/Ctrl+A → copy)",
                    value=r["text"],
                    height=200,
                    key=f"et_text_{i}",
                )
                st.download_button(
                    label="⬇️ Download .txt",
                    data=r["text"].encode("utf-8"),
                    file_name=os.path.splitext(r["name"])[0] + ".txt",
                    mime="text/plain",
                    key=f"et_dl_{i}",
                )
                st.markdown("---")

            # Combined download when several files were transcribed
            et_ok = [r for r in st.session_state.et_results if not r["error"]]
            if len(et_ok) > 1:
                combined = "\n\n".join(
                    f"===== {r['name']} =====\n{r['text']}" for r in et_ok
                )
                st.download_button(
                    label=f"⬇️ Download ALL as one .txt ({len(et_ok)} files)",
                    data=combined.encode("utf-8"),
                    file_name=f"transcriptions_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    key="et_dl_all",
                    use_container_width=True,
                )
        elif not et_files:
            st.info("Upload videos above, choose the language, then click **Extract Text**.")


# ============================================================
# TAB 7 — Design Studio (remove background + upscale / enhance)
# ============================================================
with tab7:
    st.header("🎨 Design Studio")
    st.markdown(
        "Clean up your designs: **remove the background** and **boost resolution & sharpness** "
        "for print-ready or high-quality export."
    )

    try:
        from PIL import Image, ImageFilter, ImageEnhance, ImageOps
        import numpy as np
        _ds_ok = True
    except ImportError:
        _ds_ok = False

    # Optional AI cutout engine (best for photos / hair / complex edges)
    try:
        from rembg import remove as _rembg_remove, new_session as _rembg_session
        _ds_ai = True
    except Exception:
        _ds_ai = False

    if not _ds_ok:
        st.error("Image tools aren't installed yet. Run this in Terminal, then restart the app:")
        st.code("pip install pillow numpy", language="bash")
    else:
        DS_MAX_PIXELS = 40_000_000   # ~40 MP output ceiling, keeps memory sane

        # ── Helpers ─────────────────────────────────────────
        @st.cache_resource(show_spinner=False)
        def ds_ai_session(model_name):
            return _rembg_session(model_name)

        def ds_load(file_bytes):
            img = Image.open(BytesIO(file_bytes))
            img = ImageOps.exif_transpose(img)      # honour phone rotation
            return img.convert("RGBA")

        def ds_edge_color(arr):
            """Dominant colour of the border band — the presumed background."""
            band = max(2, min(arr.shape[0], arr.shape[1]) // 100)
            border = np.concatenate([
                arr[:band, :, :3].reshape(-1, 3), arr[-band:, :, :3].reshape(-1, 3),
                arr[:, :band, :3].reshape(-1, 3), arr[:, -band:, :3].reshape(-1, 3),
            ]).astype(np.float32)
            med = np.median(border, axis=0)
            # re-average over the pixels that actually agree with the median,
            # so a stray object touching the frame can't drag the key colour off
            keep = np.sqrt(((border - med) ** 2).sum(axis=1)) < 40
            return border[keep].mean(axis=0) if keep.sum() > 16 else med

        def ds_edge_connected(close, max_dim=256):
            """
            Which background-coloured pixels actually touch the border?
            Flood-fills a coarse copy of the mask so the design's interior
            (white text, light panels…) never gets punched out.
            """
            h, w = close.shape
            step = max(1, int(np.ceil(max(h, w) / float(max_dim))))
            if step > 1:
                # BOX downscale = "any pixel in this block was background",
                # which keeps thin background channels connected
                small = np.array(
                    Image.fromarray((close * 255).astype(np.uint8)).resize(
                        (max(1, w // step), max(1, h // step)), Image.BOX
                    )
                ) > 0
            else:
                small = close.copy()

            reach = np.zeros_like(small)
            reach[0, :] = small[0, :]
            reach[-1, :] = small[-1, :]
            reach[:, 0] = small[:, 0]
            reach[:, -1] = small[:, -1]
            for _ in range(small.shape[0] + small.shape[1]):
                grown = reach.copy()
                grown[1:, :] |= reach[:-1, :]
                grown[:-1, :] |= reach[1:, :]
                grown[:, 1:] |= reach[:, :-1]
                grown[:, :-1] |= reach[:, 1:]
                grown &= small
                if np.array_equal(grown, reach):
                    break
                reach = grown

            if step > 1:
                reach = np.array(
                    Image.fromarray((reach * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
                ) > 0
            return reach & close

        def ds_remove_bg_colorkey(img, tolerance, feather, shrink,
                                  decontaminate=True, protect_interior=True):
            """
            Colour-key cutout for logos, mockups and flat designs.

            Two things make the edge clean rather than fringed:
              * interior protection — only background *connected to the frame*
                is removed, so raising the tolerance can't punch holes;
              * colour decontamination — a half-transparent edge pixel is
                C = a*F + (1-a)*B, so it still carries the old background's
                colour. We solve back for F, which is what kills the green/
                grey halo left around a cut-out design.
            """
            arr = np.array(img).astype(np.float32)
            rgb, orig_a = arr[:, :, :3], arr[:, :, 3]
            bg = ds_edge_color(np.array(img))

            dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))
            thr = max(1.0, tolerance / 100.0 * 255.0)

            if protect_interior:
                # anything within the threshold is a background *candidate*
                reachable = ds_edge_connected(dist <= thr)
                # push unreachable candidates far away so they stay opaque
                dist = np.where(reachable, dist, np.maximum(dist, thr * 1.5))

            # wide soft ramp: more edge pixels land in the partial-alpha band,
            # and every one of those gets decontaminated below
            alpha = np.clip((dist - thr * 0.35) / (thr * 0.65), 0.0, 1.0)

            if decontaminate:
                a3 = alpha[:, :, None]
                # clamp the divisor so near-invisible pixels can't amplify noise
                fg = (rgb - (1.0 - a3) * bg) / np.maximum(a3, 0.25)
                rgb = np.where(a3 < 0.995, np.clip(fg, 0.0, 255.0), rgb)

            a8 = np.minimum((alpha * 255).astype(np.uint8), orig_a.astype(np.uint8))
            a_img = Image.fromarray(a8, mode="L")
            if shrink > 0:
                a_img = a_img.filter(ImageFilter.MinFilter(min(9, 3 + 2 * (shrink - 1))))
            if feather > 0:
                a_img = a_img.filter(ImageFilter.GaussianBlur(feather))

            out = Image.fromarray(rgb.astype(np.uint8), mode="RGB").convert("RGBA")
            out.putalpha(a_img)
            return out

        def ds_remove_bg_ai(img, model_name, alpha_matting):
            buf = BytesIO()
            img.save(buf, format="PNG")
            kwargs = {"session": ds_ai_session(model_name)}
            if alpha_matting:
                kwargs.update(
                    alpha_matting=True,
                    alpha_matting_foreground_threshold=240,
                    alpha_matting_background_threshold=10,
                    alpha_matting_erode_size=10,
                )
            return Image.open(BytesIO(_rembg_remove(buf.getvalue(), **kwargs))).convert("RGBA")

        def ds_composite(img_rgba, bg_mode, bg_hex):
            """Put the cutout on a background (or keep it transparent)."""
            if bg_mode == "Transparent (PNG)":
                return img_rgba
            if bg_mode == "White":
                bg_hex = "#FFFFFF"
            elif bg_mode == "Black":
                bg_hex = "#000000"
            base = Image.new("RGBA", img_rgba.size, bg_hex)
            return Image.alpha_composite(base, img_rgba)

        def ds_upscale(img, target_w, sharpen_pct, denoise, contrast, saturation):
            """Progressive Lanczos upscale + unsharp masking."""
            w, h = img.size
            if target_w and target_w != w:
                ratio = target_w / float(w)
                nw, nh = int(round(w * ratio)), int(round(h * ratio))
                if nw * nh > DS_MAX_PIXELS:
                    scale = (DS_MAX_PIXELS / float(nw * nh)) ** 0.5
                    nw, nh = max(1, int(nw * scale)), max(1, int(nh * scale))
                # step up in 2x hops — much cleaner than one giant jump
                cw, ch = w, h
                while cw * 2 <= nw and ch * 2 <= nh:
                    cw, ch = cw * 2, ch * 2
                    img = img.resize((cw, ch), Image.LANCZOS)
                if (cw, ch) != (nw, nh):
                    img = img.resize((nw, nh), Image.LANCZOS)

            if denoise:
                img = img.filter(ImageFilter.SMOOTH)
            if sharpen_pct > 0:
                img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(sharpen_pct), threshold=3))
            if abs(contrast - 1.0) > 0.01:
                img = ImageEnhance.Contrast(img).enhance(contrast)
            if abs(saturation - 1.0) > 0.01:
                img = ImageEnhance.Color(img).enhance(saturation)
            return img

        def ds_encode(img, fmt, quality):
            buf = BytesIO()
            if fmt == "PNG":
                img.save(buf, format="PNG", optimize=True)
                return buf.getvalue(), "png", "image/png"
            if fmt == "WEBP":
                img.save(buf, format="WEBP", quality=quality, method=6)
                return buf.getvalue(), "webp", "image/webp"
            # JPG has no alpha — flatten onto white
            flat = Image.new("RGB", img.size, "#FFFFFF")
            flat.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            flat.save(buf, format="JPEG", quality=quality, subsampling=0, optimize=True)
            return buf.getvalue(), "jpg", "image/jpeg"

        # ── Step 1 — upload ─────────────────────────────────
        st.subheader("Step 1 — Upload Designs")
        ds_files = st.file_uploader(
            "Drop one or more images (PNG, JPG, WEBP…)",
            type=["png", "jpg", "jpeg", "webp", "bmp", "tiff"],
            accept_multiple_files=True,
            key="ds_files",
        )

        # ── Step 2 — what to do ─────────────────────────────
        st.subheader("Step 2 — What do you want to do?")
        ds_do_bg = st.checkbox("🧽 Remove the background", value=True, key="ds_do_bg")
        ds_do_up = st.checkbox("🔍 Increase quality & resolution", value=True, key="ds_do_up")

        if ds_do_bg:
            st.markdown("**Background removal**")
            engine_opts = ["Flat background (fast — logos, mockups, flat designs)"]
            if _ds_ai:
                engine_opts.insert(0, "AI cutout (best — photos, people, complex edges)")
            ds_engine = st.selectbox("Method", engine_opts, key="ds_engine")

            if ds_engine.startswith("AI"):
                ds_c1, ds_c2 = st.columns(2)
                with ds_c1:
                    ds_model = st.selectbox(
                        "Model",
                        ["u2net", "isnet-general-use", "u2netp", "silueta"],
                        help="u2net = balanced • isnet = sharpest edges • u2netp/silueta = lighter & faster",
                        key="ds_model",
                    )
                with ds_c2:
                    ds_matting = st.checkbox(
                        "Refine edges (alpha matting)", value=False,
                        help="Much better on hair and soft edges. Noticeably slower.",
                        key="ds_matting",
                    )
                ds_tol = ds_feather = ds_shrink = 0
                ds_decon = ds_protect = False
            else:
                if not _ds_ai:
                    st.caption(
                        "💡 Want AI-quality cutouts for photos and people? Install the engine "
                        "with `pip install rembg` and restart the app — a new option appears here."
                    )
                # Presets first — "Strong" is the default so a clean cut-out
                # is what you get without touching a single slider.
                DS_PRESETS = {
                    "Gentle":   (14, 0.4, 0),
                    "Balanced": (24, 0.6, 1),
                    "Strong (recommended)": (36, 0.8, 2),
                    "Maximum":  (52, 1.0, 3),
                }
                ds_preset = st.select_slider(
                    "Cleanup strength",
                    options=list(DS_PRESETS.keys()) + ["Custom"],
                    value=PARAMS.get("design_preset", "Strong (recommended)"),
                    key="ds_preset",
                    help="Start at Strong. Go up to Maximum if any background survives; "
                         "drop to Balanced/Gentle if the design itself gets eaten.",
                )
                if ds_preset == "Custom":
                    ds_b1, ds_b2, ds_b3 = st.columns(3)
                    with ds_b1:
                        ds_tol = st.slider("Tolerance", 1, 80, 36, key="ds_tol",
                                           help="How different from the background a pixel must be to be kept. Raise it if bits of background survive.")
                    with ds_b2:
                        ds_feather = st.slider("Edge softness", 0.0, 3.0, 0.8, 0.1, key="ds_feather")
                    with ds_b3:
                        ds_shrink = st.select_slider("Trim halo", options=[0, 1, 2, 3], value=2, key="ds_shrink",
                                                     help="Shaves the leftover background fringe around the edge.")
                else:
                    ds_tol, ds_feather, ds_shrink = DS_PRESETS[ds_preset]

                ds_q1, ds_q2 = st.columns(2)
                with ds_q1:
                    ds_decon = st.checkbox(
                        "🎯 Kill colour fringe", value=True, key="ds_decon",
                        help="Un-blends the old background out of the semi-transparent edge "
                             "pixels. This is what removes the green/grey outline around a cut-out.",
                    )
                with ds_q2:
                    ds_protect = st.checkbox(
                        "🛡️ Protect design interior", value=True, key="ds_protect",
                        help="Only removes background that touches the edge of the image, so a "
                             "high strength can't punch holes through light areas of your design.",
                    )
                ds_model, ds_matting = "u2net", False

            ds_bg_mode = st.radio(
                "New background",
                ["Transparent (PNG)", "White", "Black", "Custom colour"],
                horizontal=True, key="ds_bg_mode",
            )
            ds_bg_hex = st.color_picker("Pick a colour", "#FFFFFF", key="ds_bg_hex") \
                if ds_bg_mode == "Custom colour" else "#FFFFFF"
        else:
            ds_engine, ds_model, ds_matting = "", "u2net", False
            ds_tol, ds_feather, ds_shrink = 36, 0.8, 2
            ds_decon, ds_protect = True, True
            ds_bg_mode, ds_bg_hex = "Transparent (PNG)", "#FFFFFF"

        if ds_do_up:
            st.markdown("**Quality & resolution**")
            ds_u1, ds_u2 = st.columns(2)
            with ds_u1:
                ds_scale_mode = st.radio("Resize by", ["Multiplier", "Exact width"],
                                         horizontal=True, key="ds_scale_mode")
                if ds_scale_mode == "Multiplier":
                    ds_mult = st.select_slider("Scale", options=[1, 2, 3, 4, 6, 8], value=2, key="ds_mult")
                    ds_target_w = 0
                else:
                    ds_target_w = st.number_input("Target width (px)", 100, 12000, 2048, 64, key="ds_target_w")
                    ds_mult = 1
            with ds_u2:
                ds_sharpen = st.slider("Sharpening", 0, 250, 110, 10, key="ds_sharpen",
                                       help="Counteracts the softness that any upscale introduces.")
                ds_denoise = st.checkbox("Smooth out noise / JPEG artefacts", value=False, key="ds_denoise")

            ds_e1, ds_e2 = st.columns(2)
            with ds_e1:
                ds_contrast = st.slider("Contrast", 0.5, 2.0, 1.0, 0.05, key="ds_contrast")
            with ds_e2:
                ds_saturation = st.slider("Colour punch", 0.0, 2.0, 1.0, 0.05, key="ds_saturation")
        else:
            ds_scale_mode, ds_mult, ds_target_w = "Multiplier", 1, 0
            ds_sharpen, ds_denoise, ds_contrast, ds_saturation = 0, False, 1.0, 1.0

        # ── Step 3 — output ─────────────────────────────────
        st.subheader("Step 3 — Output")
        ds_o1, ds_o2 = st.columns(2)
        with ds_o1:
            _fmt_default = 0 if (ds_do_bg and ds_bg_mode == "Transparent (PNG)") else 0
            ds_fmt = st.selectbox("Format", ["PNG", "JPG", "WEBP"], index=_fmt_default, key="ds_fmt",
                                  help="PNG and WEBP keep transparency. JPG does not.")
        with ds_o2:
            ds_quality = st.slider("Quality (JPG / WEBP)", 60, 100, 95, key="ds_quality",
                                   disabled=(ds_fmt == "PNG"))

        if ds_do_bg and ds_bg_mode == "Transparent (PNG)" and ds_fmt == "JPG":
            st.warning("JPG can't store transparency — the cut-out background will come out white.")

        # ── Run ─────────────────────────────────────────────
        if st.button("✨ Process Designs", type="primary", use_container_width=True,
                     disabled=not ds_files, key="ds_run"):
            if not ds_do_bg and not ds_do_up:
                st.warning("Pick at least one thing to do — remove the background, boost quality, or both.")
            else:
                results, prog, status = [], st.progress(0.0), st.empty()
                for i, f in enumerate(ds_files):
                    status.info(f"Processing **{f.name}** ({i + 1}/{len(ds_files)})…")
                    try:
                        original = ds_load(f.getvalue())
                        img = original

                        if ds_do_bg:
                            if ds_engine.startswith("AI"):
                                img = ds_remove_bg_ai(img, ds_model, ds_matting)
                            else:
                                img = ds_remove_bg_colorkey(
                                    img, ds_tol, ds_feather, ds_shrink,
                                    decontaminate=ds_decon, protect_interior=ds_protect,
                                )
                            img = ds_composite(img, ds_bg_mode, ds_bg_hex)

                        if ds_do_up:
                            tw = ds_target_w if ds_scale_mode == "Exact width" else img.width * ds_mult
                            img = ds_upscale(img, tw, ds_sharpen, ds_denoise, ds_contrast, ds_saturation)

                        # sanity check: a colour-key on a photo wipes everything
                        kept = None
                        if ds_do_bg and not ds_engine.startswith("AI") and img.mode == "RGBA":
                            kept = float((np.array(img)[:, :, 3] > 128).mean() * 100.0)

                        data, ext, mime = ds_encode(img, ds_fmt, ds_quality)
                        results.append({
                            "name": f.name, "error": None, "data": data, "ext": ext, "mime": mime,
                            "before": f"{original.width}×{original.height}",
                            "after": f"{img.width}×{img.height}",
                            "size_kb": len(data) / 1024,
                            "kept": kept,
                            "preview": data,
                        })
                    except Exception as e:
                        results.append({"name": f.name, "error": str(e)})
                    prog.progress((i + 1) / len(ds_files))

                status.empty()
                prog.empty()
                st.session_state.ds_results = results

        # ── Results ─────────────────────────────────────────
        if st.session_state.get("ds_results"):
            ok = [r for r in st.session_state.ds_results if not r["error"]]
            bad = [r for r in st.session_state.ds_results if r["error"]]

            if ok:
                st.success(f"✅ Done — {len(ok)} image(s) processed.")
            for r in bad:
                st.error(f"❌ {r['name']} — {r['error']}")

            for i, r in enumerate(ok):
                st.markdown("---")
                st.markdown(f"**{r['name']}** — {r['before']} → **{r['after']}** · {r['size_kb']:.0f} KB")
                if r.get("kept") is not None and r["kept"] < 8:
                    st.warning(
                        f"Only {r['kept']:.0f}% of this image survived — it probably doesn't have a "
                        "flat background. Lower the **Cleanup strength**, or use the **AI cutout** "
                        "method (`pip install rembg`) which handles photos properly."
                    )
                pc1, pc2 = st.columns([3, 1])
                with pc1:
                    st.image(r["preview"], use_container_width=True)
                with pc2:
                    base = os.path.splitext(r["name"])[0]
                    st.download_button(
                        "⬇️ Download",
                        data=r["data"],
                        file_name=f"{base}_studio.{r['ext']}",
                        mime=r["mime"],
                        key=f"ds_dl_{i}",
                        use_container_width=True,
                    )

            if len(ok) > 1:
                zip_buf = BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for r in ok:
                        zf.writestr(f"{os.path.splitext(r['name'])[0]}_studio.{r['ext']}", r["data"])
                st.markdown("---")
                st.download_button(
                    f"📦 Download ALL as ZIP ({len(ok)} images)",
                    data=zip_buf.getvalue(),
                    file_name=f"designs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip",
                    key="ds_dl_zip",
                    use_container_width=True,
                )
        elif not ds_files:
            st.info("Upload your designs above, choose what to do, then click **Process Designs**.")


# ============================================================
# TAB 8 — Saudi Voice (text → speech, Groq / Orpheus Arabic-Saudi)
# ============================================================
with tab8:
    st.header("🗣️ Saudi Voice — Text to Speech")
    st.markdown(
        "Turn a script into natural **Saudi Arabic** narration for your videos. "
        "Six native voices, powered by Orpheus on Groq."
    )

    TTS_MODEL = PARAMS.get("tts_model", "canopylabs/orpheus-arabic-saudi")
    TTS_VOICES = {
        "فهد — Fahad (male)":       "fahad",
        "سلطان — Sultan (male)":    "sultan",
        "عبدالله — Abdullah (male)": "abdullah",
        "نورة — Noura (female)":    "noura",
        "لولوة — Lulwa (female)":   "lulwa",
        "عائشة — Aisha (female)":   "aisha",
    }
    TTS_CHUNK_CHARS = int(PARAMS.get("tts_chunk_chars", 550))   # keeps the request count low

    try:
        from groq import Groq
        _tts_ok = True
    except ImportError:
        _tts_ok = False

    # ── API key: secrets → env → manual entry. Never hard-coded. ──
    def tts_get_key():
        k, src = cfg_api_key("groq_api_key", "GROQ_API_KEY")
        if k:
            return k, src
        return st.session_state.get("tts_manual_key", ""), "this session"

    if not _tts_ok:
        st.error("The Groq client isn't installed yet. Run this in Terminal, then restart the app:")
        st.code("pip install groq", language="bash")
    else:
        tts_key, tts_key_src = tts_get_key()
        if not tts_key:
            st.warning(
                "No Groq API key found. Add it to `.streamlit/secrets.toml` as "
                "`GROQ_API_KEY = \"gsk_…\"` (recommended), or paste it below for this session."
            )
            st.text_input("Groq API key", type="password", key="tts_manual_key",
                          placeholder="gsk_…")
            tts_key, tts_key_src = tts_get_key()
        else:
            st.caption(f"🔑 Using the Groq key from **{tts_key_src}**.")

        # ── helpers ─────────────────────────────────────────
        def tts_wav_parts(data):
            """(pcm, rate, channels, sampwidth) — tolerant of the placeholder
            length Groq writes into its streamed WAV header."""
            import struct
            if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
                raise ValueError("the API did not return WAV audio")
            pos, n = 12, len(data)
            rate = ch = sw = None
            pcm = b""
            while pos + 8 <= n:
                cid = data[pos:pos + 4]
                (csz,) = struct.unpack("<I", data[pos + 4:pos + 8])
                body = pos + 8
                if cid == b"fmt ":
                    _f, ch, rate, _br, _ba, bits = struct.unpack("<HHIIHH", data[body:body + 16])
                    sw = bits // 8
                elif cid == b"data":
                    pcm = data[body:body + min(csz, n - body)]   # clamp the placeholder
                    break
                pos = body + csz + (csz & 1)
            if rate is None or not pcm:
                raise ValueError("no audio data in the response")
            return pcm, rate, ch, sw

        def tts_join_wavs(chunks, gap_ms=140):
            """Concatenate WAV payloads into one valid WAV with a short pause between."""
            import wave
            pcms, rate, ch, sw = [], None, None, None
            for c in chunks:
                p, r, c2, s = tts_wav_parts(c)
                if rate is None:
                    rate, ch, sw = r, c2, s
                pcms.append(p)
            silence = b"\x00" * (int(rate * gap_ms / 1000) * ch * sw)
            body = silence.join(pcms)
            out = BytesIO()
            with wave.open(out, "wb") as w:
                w.setnchannels(ch); w.setsampwidth(sw); w.setframerate(rate)
                w.writeframes(body)
            return out.getvalue(), len(body) / float(rate * ch * sw)

        _TTS_SPLIT = re.compile(r"(?<=[\.\!\?؟۔،\:\;])\s+|\n+")

        def tts_chunk_text(text, limit=TTS_CHUNK_CHARS):
            """Split on Arabic + Latin sentence boundaries into <=limit-char pieces."""
            text = (text or "").strip()
            if not text:
                return []
            pieces, buf = [], ""
            for part in [p for p in _TTS_SPLIT.split(text) if p and p.strip()]:
                part = part.strip()
                while len(part) > limit:                      # one very long sentence
                    cut = part.rfind(" ", 0, limit)
                    cut = cut if cut > limit * 0.5 else limit
                    if buf:
                        pieces.append(buf); buf = ""
                    pieces.append(part[:cut].strip()); part = part[cut:].strip()
                if not buf:
                    buf = part
                elif len(buf) + 1 + len(part) <= limit:
                    buf += " " + part
                else:
                    pieces.append(buf); buf = part
            if buf:
                pieces.append(buf)
            return pieces

        def tts_speak(client, text, voice, tries=4):
            """One chunk → WAV bytes, backing off through Groq's 1200 TPM limit."""
            last = None
            for attempt in range(tries):
                try:
                    r = client.audio.speech.create(
                        model=TTS_MODEL, voice=voice, input=text, response_format="wav",
                    )
                    return r.read()
                except Exception as e:
                    last = e
                    msg = str(e)
                    if "rate limit" in msg.lower() or "429" in msg:
                        m = re.search(r"try again in ([\d\.]+)s", msg)
                        time.sleep(min(60.0, float(m.group(1)) + 1.0 if m else 10.0 * (attempt + 1)))
                    elif attempt < tries - 1:
                        time.sleep(3.0 * (attempt + 1))
                    else:
                        break
            raise last

        def tts_postprocess(wav_bytes, speed, fmt):
            """Speed change + format conversion via ffmpeg (the API ignores `speed`)."""
            if abs(speed - 1.0) < 0.01 and fmt == "WAV":
                return wav_bytes, "wav", "audio/wav"
            ext = "mp3" if fmt == "MP3" else "wav"
            with tempfile.TemporaryDirectory() as td:
                src = os.path.join(td, "in.wav")
                dst = os.path.join(td, f"out.{ext}")
                with open(src, "wb") as fh:
                    fh.write(wav_bytes)
                cmd = [FFMPEG, "-y", "-i", src]
                if abs(speed - 1.0) >= 0.01:
                    cmd += ["-filter:a", f"atempo={speed:.2f}"]
                if ext == "mp3":
                    cmd += ["-codec:a", "libmp3lame", "-b:a", "192k"]
                cmd += [dst]
                p = subprocess.run(cmd, capture_output=True)
                if p.returncode != 0 or not os.path.exists(dst):
                    # ffmpeg unavailable or unhappy — hand back the untouched WAV
                    return wav_bytes, "wav", "audio/wav"
                with open(dst, "rb") as fh:
                    return fh.read(), ext, ("audio/mpeg" if ext == "mp3" else "audio/wav")

        # ── Step 1 — script ─────────────────────────────────
        st.subheader("Step 1 — Your Script")

        # convenience: reuse whatever the Extract Text tab produced
        _et = [r for r in st.session_state.get("et_results", []) if not r.get("error")]
        if _et:
            _pick = st.selectbox(
                "Reuse a transcription from the Extract Text tab (optional)",
                ["— none —"] + [r["name"] for r in _et], key="tts_reuse",
            )
            if _pick != "— none —" and st.button("⬅️ Load that text", key="tts_load_et"):
                st.session_state.tts_text = next(r["text"] for r in _et if r["name"] == _pick)
                st.rerun()

        tts_text = st.text_area(
            "Text to speak (Arabic or English)",
            height=180, key="tts_text",
            placeholder="اكتب النص هنا… مثال: أهلاً وسهلاً بكم في قناتنا، اليوم عندنا موضوع مهم جداً.",
        )

        _chunks = tts_chunk_text(tts_text)
        if tts_text:
            _mins = len(tts_text) / 900.0
            st.caption(
                f"📝 {len(tts_text)} characters · {len(_chunks)} request(s) · roughly "
                f"{_mins:.1f} min of audio"
            )

        # ── Step 2 — voice ──────────────────────────────────
        st.subheader("Step 2 — Voice & Delivery")
        tv1, tv2, tv3 = st.columns([2, 1, 1])
        with tv1:
            _vnames = list(TTS_VOICES.keys())
            _vdef = PARAMS.get("tts_default_voice", "fahad")
            _vidx = next((i for i, n in enumerate(_vnames) if TTS_VOICES[n] == _vdef), 0)
            tts_voice_label = st.selectbox("Voice", _vnames, index=_vidx, key="tts_voice")
        with tv2:
            tts_speed = st.slider("Speed", 0.5, 2.0, 1.0, 0.05, key="tts_speed",
                                  help="Applied locally with ffmpeg — the model itself always "
                                       "speaks at its natural pace.")
        with tv3:
            tts_fmt = st.selectbox("Format", ["MP3", "WAV"], key="tts_fmt",
                                   help="MP3 needs ffmpeg. WAV is always available.")
        tts_gap = st.slider("Pause between sentences (ms)", 0, 600,
                            int(PARAMS.get("tts_gap_ms", 140)), 20, key="tts_gap",
                            help="Only matters when the script is long enough to be split.")

        # ── Generate ────────────────────────────────────────
        if st.button("🎙️ Generate Voice", type="primary", use_container_width=True,
                     disabled=not (tts_text and tts_text.strip() and tts_key), key="tts_run"):
            try:
                client = Groq(api_key=tts_key)
                prog, status = st.progress(0.0), st.empty()
                parts, failed = [], None
                for i, piece in enumerate(_chunks):
                    status.info(f"Speaking part {i + 1} of {len(_chunks)}…")
                    try:
                        parts.append(tts_speak(client, piece, TTS_VOICES[tts_voice_label]))
                    except Exception as e:
                        failed = f"Part {i + 1} failed: {e}"
                        break
                    prog.progress((i + 1) / len(_chunks))
                status.empty(); prog.empty()

                if failed and not parts:
                    st.error(f"❌ {failed}")
                    st.session_state.tts_audio = None
                else:
                    if failed:
                        st.warning(f"⚠️ {failed} — keeping the {len(parts)} part(s) that worked.")
                    joined, dur = tts_join_wavs(parts, tts_gap)
                    data, ext, mime = tts_postprocess(joined, tts_speed, tts_fmt)
                    st.session_state.tts_audio = {
                        "data": data, "ext": ext, "mime": mime,
                        "dur": dur / max(tts_speed, 0.01),
                        "voice": tts_voice_label, "parts": len(parts),
                    }
            except Exception as e:
                st.error(f"❌ {e}")
                st.session_state.tts_audio = None

        # ── Result ──────────────────────────────────────────
        _a = st.session_state.get("tts_audio")
        if _a:
            st.success(
                f"✅ Done — {_a['dur']:.1f}s of audio in **{_a['voice']}** "
                f"({_a['parts']} part(s), {len(_a['data']) / 1024:.0f} KB)."
            )
            st.audio(_a["data"], format=_a["mime"])
            st.download_button(
                "⬇️ Download audio",
                data=_a["data"],
                file_name=f"saudi_voice_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{_a['ext']}",
                mime=_a["mime"],
                use_container_width=True,
                key="tts_dl",
            )
        elif not tts_text:
            st.info("Write or paste your script above, pick a voice, then hit **Generate Voice**.")


# ============================================================
# ADMIN — login-gated settings dashboard
# ============================================================
with admin_tab:
    if not st.session_state.get("is_admin"):
        st.header("⚙️ Admin")
        st.markdown("Sign in to manage API keys, tool visibility and defaults.")
        _l1, _l2 = st.columns([1, 1])
        with _l1:
            _u = st.text_input("Username", key="adm_user")
            _p = st.text_input("Password", type="password", key="adm_pass")
            if st.button("🔓 Sign in", type="primary", key="adm_login"):
                if _u.strip() == CFG["admin"]["username"] and _sha(_p) == CFG["admin"]["password_hash"]:
                    st.session_state.is_admin = True
                    st.rerun()
                else:
                    st.error("Wrong username or password.")
        with _l2:
            st.info(
                "This gate only hides the settings panel — it is not real "
                "security. Anyone who can open the app can still use the tools, "
                "and anyone with access to the server can read the key file. "
                "Don't treat it as protection for a public deployment."
            )
    else:
        _h1, _h2 = st.columns([4, 1])
        with _h1:
            st.header("⚙️ Admin Dashboard")
            st.caption(f"Signed in as **{CFG['admin']['username']}**")
        with _h2:
            if st.button("Sign out", key="adm_logout", use_container_width=True):
                st.session_state.is_admin = False
                st.rerun()

        # ── API keys ────────────────────────────────────────
        st.subheader("🔑 API Keys")
        st.caption(
            f"Saved to `{CONFIG_FILE}` on this machine. That file is gitignored — "
            "it is never committed. On Streamlit Cloud the filesystem resets on "
            "redeploy, so there use **Settings → Secrets** instead."
        )
        _k1, _k2 = st.columns(2)
        with _k1:
            _groq = st.text_input(
                "Groq API key — powers 🗣️ Saudi Voice", type="password",
                value=CFG["api"].get("groq_api_key", ""),
                placeholder="gsk_…", key="adm_groq",
            )
        with _k2:
            _serp = st.text_input(
                "SerpAPI key — powers 🔍 Find Similar", type="password",
                value=CFG["api"].get("serpapi_key", ""),
                placeholder="Your SerpAPI key", key="adm_serp",
            )
        _live_groq, _src_groq = cfg_api_key("groq_api_key", "GROQ_API_KEY")
        _live_serp, _src_serp = cfg_api_key("serpapi_key", "SERPAPI_KEY")
        st.caption(
            f"Groq: {'✅ active via ' + _src_groq if _live_groq else '❌ not set'} · "
            f"SerpAPI: {'✅ active via ' + _src_serp if _live_serp else '❌ not set'}"
        )
        if st.button("💾 Save API keys", type="primary", key="adm_save_keys"):
            CFG["api"]["groq_api_key"] = _groq.strip()
            CFG["api"]["serpapi_key"] = _serp.strip()
            save_config(CFG)
            st.success("Saved.")
            st.rerun()

        # ── Visible tools ───────────────────────────────────
        st.subheader("🧩 Tools Shown in the App")
        st.caption("Untick a tool to hide its tab from everyone.")
        _tcols = st.columns(4)
        _new_tools = {}
        for _i, (_key, _label) in enumerate(TOOL_REGISTRY):
            with _tcols[_i % 4]:
                _new_tools[_key] = st.checkbox(
                    _label, value=CFG["tools"].get(_key, True), key=f"adm_tool_{_key}"
                )
        if not any(_new_tools.values()):
            st.warning("At least one tool has to stay visible.")
        if st.button("💾 Save visible tools", type="primary", key="adm_save_tools",
                     disabled=not any(_new_tools.values())):
            CFG["tools"] = _new_tools
            save_config(CFG)
            st.success("Saved.")
            st.rerun()

        # ── Defaults ────────────────────────────────────────
        st.subheader("🎚️ Default Parameters")
        _p1, _p2 = st.columns(2)
        with _p1:
            st.markdown("**🗣️ Saudi Voice**")
            _m_model = st.text_input("Groq TTS model", value=PARAMS.get("tts_model", ""),
                                     key="adm_model")
            _m_voice = st.selectbox(
                "Default voice",
                ["fahad", "sultan", "abdullah", "noura", "lulwa", "aisha"],
                index=["fahad", "sultan", "abdullah", "noura", "lulwa", "aisha"].index(
                    PARAMS.get("tts_default_voice", "fahad")
                ) if PARAMS.get("tts_default_voice", "fahad") in
                     ["fahad", "sultan", "abdullah", "noura", "lulwa", "aisha"] else 0,
                key="adm_voice",
            )
            _m_chunk = st.slider("Characters per request", 200, 900,
                                 int(PARAMS.get("tts_chunk_chars", 550)), 50, key="adm_chunk",
                                 help="Bigger chunks = fewer requests against Groq's quota, "
                                      "but a higher chance of hitting the per-minute token limit.")
            _m_gap = st.slider("Default pause between sentences (ms)", 0, 600,
                               int(PARAMS.get("tts_gap_ms", 140)), 20, key="adm_gap")
        with _p2:
            st.markdown("**🔄 Refresh Metadata**")
            _m_days = st.slider("Back-date timestamps up to (days)", 1, 60,
                                int(PARAMS.get("meta_days_back", 10)), 1, key="adm_days")
            st.markdown("**🎨 Design Studio**")
            _m_preset = st.select_slider(
                "Default cleanup strength",
                options=["Gentle", "Balanced", "Strong (recommended)", "Maximum"],
                value=PARAMS.get("design_preset", "Strong (recommended)"), key="adm_preset",
            )
            st.markdown("**🏷️ Branding**")
            _m_title = st.text_input("App title", value=PARAMS.get("app_title", "TikTok Studio"),
                                     key="adm_title")
            _m_tag = st.text_area("Tagline", value=PARAMS.get("app_tagline", ""), height=80,
                                  key="adm_tagline")

        if st.button("💾 Save parameters", type="primary", key="adm_save_params"):
            CFG["params"].update({
                "tts_model": _m_model.strip() or "canopylabs/orpheus-arabic-saudi",
                "tts_default_voice": _m_voice,
                "tts_chunk_chars": int(_m_chunk),
                "tts_gap_ms": int(_m_gap),
                "meta_days_back": int(_m_days),
                "design_preset": _m_preset,
                "app_title": _m_title.strip() or "TikTok Studio",
                "app_tagline": _m_tag.strip(),
            })
            save_config(CFG)
            st.success("Saved.")
            st.rerun()

        # ── Account ─────────────────────────────────────────
        st.subheader("👤 Admin Account")
        _a1, _a2, _a3 = st.columns(3)
        with _a1:
            _n_user = st.text_input("Username", value=CFG["admin"]["username"], key="adm_newuser")
        with _a2:
            _n_pw = st.text_input("New password", type="password", key="adm_newpw")
        with _a3:
            _n_pw2 = st.text_input("Confirm password", type="password", key="adm_newpw2")
        if st.button("💾 Update credentials", key="adm_save_cred"):
            if not _n_user.strip():
                st.error("The username can't be empty.")
            elif _n_pw and _n_pw != _n_pw2:
                st.error("The two passwords don't match.")
            else:
                CFG["admin"]["username"] = _n_user.strip()
                if _n_pw:
                    CFG["admin"]["password_hash"] = _sha(_n_pw)
                save_config(CFG)
                st.success("Updated." + ("" if _n_pw else " (password unchanged)"))
                st.rerun()

        # ── Config file ─────────────────────────────────────
        st.subheader("💾 Configuration File")
        _safe = json.loads(json.dumps(CFG))
        _safe["api"] = {k: ("•" * 8 + v[-4:] if v else "") for k, v in _safe["api"].items()}
        _safe["admin"]["password_hash"] = "•" * 16
        with st.expander("Show current configuration (keys masked)"):
            st.json(_safe)
        st.download_button(
            "⬇️ Download backup (includes real keys — keep it private)",
            data=json.dumps(CFG, indent=2, ensure_ascii=False).encode("utf-8"),
            file_name="studio_config_backup.json", mime="application/json",
            key="adm_backup", use_container_width=True,
        )
        _restore = st.file_uploader("Restore from a backup", type=["json"], key="adm_restore")
        if _restore and st.button("♻️ Restore this file", key="adm_do_restore"):
            try:
                save_config(json.loads(_restore.getvalue().decode("utf-8")))
                st.success("Restored.")
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't read that file: {e}")
