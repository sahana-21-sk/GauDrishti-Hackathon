"""Helpers for the Streamlit app.

RULE: the UI adapts to the FROZEN backend (colab/, SCHEMA.md, data/live/). Nothing in this file edits them.
Every function fails safe, so nothing here can crash the UI.
"""
import base64, copy, io, json, os, subprocess, sys, tempfile, zipfile
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
LIVE, DEMO, AUDIO, COLAB = ROOT / "data" / "live", ROOT / "data" / "demo", ROOT / "data" / "audio", ROOT / "colab"
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

LANGS = {"English": "en", "हिन्दी (Hindi)": "hi", "తెలుగు (Telugu)": "te"}
LANG_NAME = {"en": "English", "hi": "Hindi", "te": "Telugu"}

STATE_COLORS = {"walking": "#F59E0B", "feeding": "#16A34A", "standing": "#9CA3AF", "lying": "#2563EB"}
STATE_ORDER = ["walking", "feeding", "standing", "lying"]
STATUS_COLORS = {"alert": "#DC2626", "watch": "#F59E0B", "normal": "#16A34A"}
STATUS_LABEL = {"alert": "ALERT", "watch": "WATCHLIST", "normal": "NORMAL"}
STATUS_ICON = {"alert": "🔴", "watch": "🟡", "normal": "🟢"}

_cache = getattr(st, "cache_data", None) or (lambda **k: (lambda f: f))


# ------------------------------------------------------------------ loading
def thresholds():
    """Alert thresholds, READ from the frozen analysis.py (never written). Falls back to its documented defaults."""
    t = dict(heat_alert=0.5, health_alert=0.4, watch_from=0.30)
    try:
        if str(COLAB) not in sys.path:
            sys.path.insert(0, str(COLAB))
        from analysis import CFG
        t["heat_alert"], t["health_alert"] = float(CFG["heat_alert"]), float(CFG["health_alert"])
    except Exception:
        pass
    return t


def normalize(res):
    """Return a safe in-memory copy. The JSON on disk is never changed.
    Compatibility: the frozen backend's watchlist items have no 'type'; give them one so the UI can treat all items alike."""
    r = copy.deepcopy(res)
    r.setdefault("events", [])
    r.setdefault("alerts", [])
    r.setdefault("watchlist", [])
    for a in r["alerts"]:
        a["kind"] = "alert"
        a.setdefault("reasons", [])
    for w in r["watchlist"]:
        w["kind"] = "watch"
        w.setdefault("type", "watch")
        w.setdefault("reasons", [])
    return r


def _valid(res):
    return isinstance(res, dict) and all(k in res for k in ("meta", "cows", "alerts")) and bool(res["cows"])


def load_results(source="auto"):
    """source: 'auto' (live, then demo) | 'demo' | 'mine' (analysis from this session). Returns (results, folder, label)."""
    mine = st.session_state.get("analysis")
    if source == "mine" and mine:
        return normalize(mine[0]), mine[1], "My analysis"
    order = [("Demo herd", DEMO)] if source == "demo" else [("Live results", LIVE), ("Demo herd", DEMO)]
    for label, folder in order:
        p = folder / "results.json"
        try:
            if p.exists():
                res = json.loads(p.read_text(encoding="utf-8"))
                if _valid(res):
                    return normalize(res), folder, label
        except Exception:
            pass
    return None, DEMO, "No data"


def media(folder, rel):
    try:
        if rel and (Path(folder) / rel).exists():
            return str(Path(folder) / rel)
    except Exception:
        pass
    return None


@_cache(show_spinner=False)
def frame_jpeg_b64(path, t=0.0, width=960):
    """One frame of a video as base64 JPEG (for the optional map background). Returns None on any problem."""
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            return None
        h, w = frame.shape[:2]
        frame = cv2.resize(frame, (width, int(h * width / w)))
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return base64.b64encode(buf.tobytes()).decode() if ok else None
    except Exception:
        return None


# ------------------------------------------------------------------ numbers shown in the UI
def breeding_window(hour):
    """AM-PM rule: heat seen in the morning -> breed this evening; seen in the afternoon/evening -> next morning."""
    return "today 4 PM to 8 PM" if hour < 12 else "tomorrow 6 AM to 10 AM"


def all_items(res):
    return list(res.get("alerts", [])) + list(res.get("watchlist", []))


def cow_status(res, cid):
    if any(a["cow_id"] == cid for a in res.get("alerts", [])):
        return "alert"
    if any(w["cow_id"] == cid for w in res.get("watchlist", [])):
        return "watch"
    return "normal"


def status_counts(res):
    out = {"alert": 0, "watch": 0, "normal": 0}
    for c in res["cows"]:
        out[cow_status(res, c["id"])] += 1
    return out


def herd_pulse(res):
    """0-100. Each cow starts at 100. A formal alert costs up to 60 points (score x 60); a watchlist case up to 35 (score x 35)."""
    loss = {}
    for a in res.get("alerts", []):
        loss[a["cow_id"]] = max(loss.get(a["cow_id"], 0), 60 * a["score"])
    for w in res.get("watchlist", []):
        loss[w["cow_id"]] = max(loss.get(w["cow_id"], 0), 35 * w["score"])
    ids = [c["id"] for c in res["cows"]]
    return round(sum(100 - loss.get(i, 0) for i in ids) / max(len(ids), 1))


def pct_change(new, old):
    return 0.0 if abs(old) < 1e-4 else (new - old) / old * 100.0


def cow_rows(res):
    """One dict per cow: everything the herd table and charts need."""
    rows = []
    for c in res["cows"]:
        s = c["stats"]
        b, r = s["baseline"], s["recent"]
        st_ = cow_status(res, c["id"])
        rows.append(dict(
            cow=c["id"], status=st_, label=f"{STATUS_ICON[st_]} {STATUS_LABEL[st_]}",
            health=round(s.get("health_score", 0) * 100), heat=round(s.get("heat_score", 0) * 100),
            move_pct=round(pct_change(r["speed"], b["speed"])),
            feed_pct=round(pct_change(r["feeding_pct"], b["feeding_pct"])),
            lying_pts=round((r["lying_pct"] - b["lying_pct"]) * 100),
            isolation=round(s.get("isolation_score", 0) * 100), mounts=s.get("mount_events", 0)))
    return rows


def state_shares(cow, split):
    """% of seconds in each behaviour: during her baseline vs afterwards (same fallback rule as the backend)."""
    tl = cow["timeline"]
    base = [p for p in tl if p["t"] < split]
    rec = [p for p in tl if p["t"] >= split]
    if len(base) < 2 or len(rec) < 2:
        base = rec = tl

    def share(part):
        n = max(len(part), 1)
        return {s: round(100 * sum(p["state"] == s for p in part) / n) for s in STATE_ORDER}
    return share(base), share(rec)


def live_check():
    """Compares data/live with the known-good verified demo (2 cows, 1 watchlist, 0 alerts, Cow #2 ~0.39).
    Returns (ok, [(label, passed)]) or None if there are no live results."""
    p = LIVE / "results.json"
    try:
        if not p.exists():
            return None
        r = json.loads(p.read_text(encoding="utf-8"))
        w = r.get("watchlist", [])
        w2 = next((x for x in w if x.get("cow_id") == 2), {})
        why = " ".join(w2.get("reasons", []))
        checks = [("Cows tracked = 2", len(r.get("cows", [])) == 2), ("Watchlist = 1", len(w) == 1),
                  ("Alerts = 0", len(r.get("alerts", [])) == 0), ("Cow #2 score about 0.39", abs(w2.get("score", 0) - 0.39) < 0.02),
                  ("Movement 18% lower", "Movement 18% lower" in why), ("Feeding time down 70%", "Feeding time down 70%" in why)]
        return all(ok for _, ok in checks), checks
    except Exception:
        return None


# ------------------------------------------------------------------ explanation (Gemini, with template fallback) + voice
def _fallback(item, lang, window):
    i, why = item["cow_id"], "; ".join(item.get("reasons", []))
    score = int(item["score"] * 100)
    if item.get("kind") == "watch":
        return {"hi": f"गाय #{i} निगरानी सूची में है। छोटे बदलाव दिखे हैं। आज उस पर नज़र रखें।",
                "te": f"ఆవు #{i} వాచ్‌లిస్ట్‌లో ఉంది. చిన్న మార్పులు కనిపించాయి. ఈ రోజు గమనిస్తూ ఉండండి."}.get(
            lang, f"Cow #{i} is on the watchlist. Small changes noticed: {why}. Keep an eye on her today; no action needed yet.\n"
                  f"Vet note: mild deviation from own baseline, score {score}%.")
    heat = item.get("type") == "heat"
    if lang == "hi":
        return (f"गाय #{i} में गर्मी (heat) के संकेत मिले हैं। प्रजनन के लिए सबसे अच्छा समय: {window}। कृपया पशु चिकित्सक से संपर्क करें।"
                if heat else f"गाय #{i} में बीमारी के शुरुआती संकेत दिखे हैं। कृपया पशु चिकित्सक से जाँच कराएँ।")
    if lang == "te":
        return (f"ఆవు #{i} లో వేడి (heat) లక్షణాలు కనిపించాయి. ఉత్తమ గర్భధారణ సమయం: {window}. దయచేసి పశువైద్యుడిని సంప్రదించండి."
                if heat else f"ఆవు #{i} లో అనారోగ్య ప్రారంభ లక్షణాలు కనిపించాయి. దయచేసి పశువైద్యుడిని సంప్రదించండి.")
    if heat:
        return (f"Cow #{i} may be in heat. Why: {why}. Best breeding window: {window}. Please call your vet.\n"
                f"Vet note: possible estrus, confidence {score}%.")
    return (f"Cow #{i} shows possible early signs of illness. Why: {why}. Please get her checked by a vet.\n"
            f"Vet note: behaviour change vs own baseline, score {score}%.")


def _secret(name):
    v = os.getenv(name)
    if v:
        return v
    try:
        return st.secrets.get(name)
    except Exception:
        return None


def _gemini(prompt):
    key = _secret("GEMINI_API_KEY")
    if not key:
        return None
    try:
        from google import genai
        r = genai.Client(api_key=key).models.generate_content(model=_secret("GEMINI_MODEL") or "gemini-3.8-flash", contents=prompt)
        return (r.text or "").strip() or None
    except Exception:
        return None

def explain(item, lang, window):
    
    try:
        cache = st.session_state.setdefault("expl", {})

        key = (
            item.get("id"),
            item.get("cow_id"),
            round(float(item.get("score", 0)), 2),
            lang,
            window,
        )

        if key not in cache:
            kind = (
                "watchlist (mild drift, no action needed yet)"
                if item.get("kind") == "watch"
                else item.get("type", "alert")
            )

            prompt = (
                "You help small dairy farmers in India. "
                "A camera system flagged a cow using these signals "
                "(this is a screening aid, not a diagnosis).\n"
                f"Type: {kind}\n"
                f"Cow: #{item.get('cow_id')}\n"
                f"Confidence: {int(float(item.get('score', 0)) * 100)}%\n"
                f"Reasons: {'; '.join(item.get('reasons', []))}\n"
                f"Best breeding window (heat only): {window}\n\n"
                f"Write in {LANG_NAME.get(lang, 'English')}: "
                "(1) two short, simple sentences for the farmer saying "
                "what was seen and what to do (use the word 'possible', "
                "never claim a diagnosis); then (2) one line starting "
                "with 'Vet note:' (in English) for the vet. "
                "Plain text, no markdown."
            )

            text = _gemini(prompt)

            if text:
                cache[key] = (text, "gemini")
            else:
                cache[key] = (_fallback(item, lang, window), "template")

        return cache[key]

    except Exception:
        return _fallback(item, lang, window), "template"

def translated_reasons(item, lang):
    """Translate alert/watchlist reasons for display without changing backend results."""
    reasons = item.get("reasons", [])

    if lang == "en":
        return reasons

    translations = {
        "hi": {
            "Movement 18% lower": "गतिशीलता 18% कम है",
            "Feeding time down 70%": "खाने का समय 70% कम है",
            "Lying time increased": "लेटने का समय बढ़ गया है",
            "Lying time decreased": "लेटने का समय कम हो गया है",
            "Isolation increased": "झुंड से अलग रहने का समय बढ़ गया है",
            "Repeated mounting": "बार-बार माउंटिंग व्यवहार देखा गया है",
            "Possible heat": "गर्मी (हीट) के संभावित संकेत दिखाई दिए हैं",
        },
        "te": {
            "Movement 18% lower": "కదలిక 18% తగ్గింది",
            "Feeding time down 70%": "తినే సమయం 70% తగ్గింది",
            "Lying time increased": "పడుకునే సమయం పెరిగింది",
            "Lying time decreased": "పడుకునే సమయం తగ్గింది",
            "Isolation increased": "మంద నుండి ఒంటరిగా ఉండే సమయం పెరిగింది",
            "Repeated mounting": "పునరావృత మౌంటింగ్ ప్రవర్తన కనిపించింది",
            "Possible heat": "వేడి (హీట్) యొక్క సంభావ్య లక్షణాలు కనిపించాయి",
        },
    }

    table = translations.get(lang, {})

    return [table.get(reason, reason) for reason in reasons]


def speak(text, lang, item_id, allow_pregen):
    """MP3 bytes or None. Pre-generated audio first (only for template text), then gTTS live."""
    try:
        f = AUDIO / f"{item_id}_{lang}.mp3"
        if allow_pregen and f.exists():
            return f.read_bytes()
    except Exception:
        pass
    try:
        from gtts import gTTS
        buf = io.BytesIO()
        gTTS(text=text.split("\nVet note:")[0], lang=lang).write_to_fp(buf)
        return buf.getvalue()
    except Exception:
        return None


# ------------------------------------------------------------------ COMPATIBILITY LAYER for video processing
# The frozen colab/process_video.py exposes only: process(video, out_dir, model, conf, feed_zone, start_clock).
# It has no video_info(), no progress callback, no stride and no threshold arguments. So the app provides those
# helpers itself and calls process() exactly as the Colab notebook does.
def engine_available():
    try:
        import cv2
        import importlib.util
        return importlib.util.find_spec("ultralytics") is not None
    except Exception:
        return False


def video_info(path):
    """Replacement for the video_info() that the V2 app expected. Returns dict(W, H, fps, n, duration)."""
    import cv2
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    info = dict(W=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), H=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), fps=fps, n=n, duration=n / fps)
    cap.release()
    return info


def first_frame_bgr(path):
    import cv2
    cap = cv2.VideoCapture(str(path))
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def trim_video(src, dst, seconds):
    """Keep only the first N seconds (done here, so the frozen pipeline is untouched). Returns dst, or src if trimming fails."""
    try:
        import imageio_ffmpeg
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(src), "-t", str(seconds), "-an",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", str(dst)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return dst
    except Exception:
        return src


def run_pipeline(video, out_dir, model, conf, feed_zone, start_clock):
    """Calls the FROZEN pipeline exactly like the Colab notebook does. Returns its results dict."""
    if str(COLAB) not in sys.path:
        sys.path.insert(0, str(COLAB))
    try:
        import torch
        torch.set_num_threads(2)   # keep the laptop responsive
    except Exception:
        pass
    from process_video import process
    return process(str(video), str(out_dir), model, conf, feed_zone, start_clock)


def load_zip_results(file_bytes):
    """Safely unzip a Colab output.zip. Returns (results, folder) or raises ValueError."""
    tmp = Path(tempfile.mkdtemp(prefix="gd_zip_"))
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
        for n in z.namelist():
            if n.startswith("/") or ".." in Path(n).parts:
                raise ValueError("Unsafe zip")
        z.extractall(tmp)
    found = list(tmp.rglob("results.json"))
    if not found:
        raise ValueError("No results.json inside this zip")
    res = json.loads(found[0].read_text(encoding="utf-8"))
    if not _valid(res):
        raise ValueError("results.json is missing cows or alerts")
    return normalize(res), found[0].parent
