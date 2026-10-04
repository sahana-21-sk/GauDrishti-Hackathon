"""Creates Demo Mode data (data/demo/) from SYNTHETIC cows. Also the reference for the results.json format."""
import json, math, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "colab"))
from analysis import build_results

FPS, W, H, T = 10, 640, 360, 40
FEED = (0, 0.75, 1, 1)


def tri(x):
    x %= 2
    return x if x <= 1 else 2 - x


def pose(i, t):
    w, h = 100, 50
    if i == 1: return 150 + 30 * math.sin(2 * math.pi * t / 19), 300, w, h
    if i == 2: return 330 + 30 * math.sin(2 * math.pi * t / 23 + 1), 305, w, h
    if i == 3:  # in heat: busy, stops feeding, gets mounted at 24-30s
        if t < 16: return 480 + 30 * math.sin(2 * math.pi * t / 19 + 2), 300, w, h
        if 24 <= t < 30: return 300, 200, w, h
        return 100 + 300 * tri(t * 60 / 300), 200, w, h
    if i == 4:
        if 24 <= t < 30: return 300, 180, w, h
        return 450 + 30 * math.sin(2 * math.pi * t / 21), 120, w, h
    if t < 16: return 200 + 24 * math.sin(2 * math.pi * t / 10), 120, w, h  # cow 5: later isolated + lying
    return 590 + 2 * math.sin(t), 40, w, 30


def synth_tracks(seed=7):
    rng, tracks = np.random.default_rng(seed), {}
    for f in range(FPS * T):
        rows = []
        for i in range(1, 6):
            cx, cy, w, h = pose(i, f / FPS)
            cx += rng.normal(0, 0.6); cy += rng.normal(0, 0.6)
            rows.append((i, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
        tracks[f] = rows
    return tracks


def build():
    return build_results(synth_tracks(), FPS, W, H, dict(feed_zone=FEED), video_name="synthetic_demo")


if __name__ == "__main__":
    from process_video import render_video, make_clips
    out = ROOT / "data" / "demo"
    out.mkdir(parents=True, exist_ok=True)
    tr, res = synth_tracks(), build()
    render_video(None, tr, res, out / "processed_video.mp4", FPS, W, H)
    make_clips(out / "processed_video.mp4", res, out)
    (out / "results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("alerts:", [(a["id"], a["cow_id"], a["type"], a["score"]) for a in res["alerts"]])
