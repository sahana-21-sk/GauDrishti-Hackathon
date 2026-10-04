"""PURE ANALYSIS (Person A). Tracks in -> results dict out. No YOLO/OpenCV here, so it is easy to test.
tracks = {frame_index: [(cow_id, x1, y1, x2, y2), ...]}"""
from collections import defaultdict
from itertools import combinations
import numpy as np

CFG = dict(
    min_seen_s=3, walk_speed=0.25, lying_height_ratio=0.8,
    feed_zone=None,          # (x1,y1,x2,y2) as fractions of frame, e.g. (0, 0.75, 1, 1)
    mount_overlap=0.45, mount_dy=0.25, mount_min_s=2,
    baseline_frac=0.4,       # first 40% of video = the cow's own "normal"
    heat_alert=0.5, health_alert=0.4,
    clip_pre=3, clip_post=5, video_start_clock="06:00",
)


def _c01(x):
    return float(min(1.0, max(0.0, x)))


def per_second(tracks, fps):
    by = defaultdict(lambda: defaultdict(list))
    for f in sorted(tracks):
        for (i, x1, y1, x2, y2) in tracks[f]:
            by[int(i)][int(f // fps)].append((x1, y1, x2, y2))
    out = {}
    for i, secs in by.items():
        d = {}
        for s, rows in secs.items():
            a = np.array(rows, float)
            cx, cy = (a[:, 0] + a[:, 2]) / 2, (a[:, 1] + a[:, 3]) / 2
            w, h = float(np.mean(a[:, 2] - a[:, 0])), float(np.mean(a[:, 3] - a[:, 1]))
            disp = float(np.hypot(cx[-1] - cx[0], cy[-1] - cy[0])) if len(a) > 1 else 0.0
            d[s] = dict(box=a.mean(0), cx=float(cx.mean()), cy=float(cy.mean()), w=w, h=h,
                        speed=disp / max(w, 1e-6))
        out[i] = d
    return out


def _overlap(A, B):
    iw = min(A[2], B[2]) - max(A[0], B[0])
    ih = min(A[3], B[3]) - max(A[1], B[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    small = min((A[2] - A[0]) * (A[3] - A[1]), (B[2] - B[0]) * (B[3] - B[1]))
    return iw * ih / small if small > 0 else 0.0


def detect_mounts(ps, c):
    cand = defaultdict(list)
    for s in sorted({s for d in ps.values() for s in d}):
        present = [i for i in ps if s in ps[i]]
        for a, b in combinations(present, 2):
            A, B = ps[a][s], ps[b][s]
            if _overlap(A["box"], B["box"]) < c["mount_overlap"]:
                continue
            up, lo = (a, b) if A["cy"] < B["cy"] else (b, a)
            U, L = ps[up][s], ps[lo][s]
            if L["cy"] - U["cy"] >= c["mount_dy"] * min(U["h"], L["h"]):
                cand[(up, lo)].append(s)
    events = []
    for (up, lo), secs in cand.items():
        secs = sorted(secs)
        run = [secs[0]]
        for s in secs[1:] + [None]:
            if s is not None and s - run[-1] <= 1:
                run.append(s)
                continue
            if len(run) >= c["mount_min_s"]:
                events.append(dict(t_start=run[0], t_end=run[-1] + 1, type="mounting",
                                   upper_id=up, lower_id=lo))
            run = [s] if s is not None else []
    return sorted(events, key=lambda e: e["t_start"])


def _metrics(tl):
    n = len(tl)
    if n == 0:
        return dict(speed=0.0, lying_pct=0.0, feeding_pct=0.0)
    return dict(speed=round(float(np.mean([p["speed"] for p in tl])), 3),
                lying_pct=round(sum(p["state"] == "lying" for p in tl) / n, 3),
                feeding_pct=round(sum(p["state"] == "feeding" for p in tl) / n, 3))


def _isolation(ps, W, H):
    diag = float(np.hypot(W, H))
    iso, seen = defaultdict(int), defaultdict(int)
    for s in sorted({s for d in ps.values() for s in d}):
        present = [i for i in ps if s in ps[i]]
        if len(present) < 3:
            continue
        pts = np.array([[ps[i][s]["cx"], ps[i][s]["cy"]] for i in present])
        dist = np.hypot(*(pts - np.median(pts, axis=0)).T)
        lim = 1.5 * max(float(np.median(dist)), 0.05 * diag)
        for i, dd in zip(present, dist):
            seen[i] += 1
            iso[i] += int(dd > lim)
    return {i: (iso[i] / seen[i] if seen[i] else 0.0) for i in ps}


def build_results(tracks, fps, W, H, cfg=None, video_name="", processed_video="processed_video.mp4"):
    c = dict(CFG)
    c.update(cfg or {})
    ps = {i: d for i, d in per_second(tracks, fps).items() if len(d) >= c["min_seen_s"]}
    T = (max(max(d) for d in ps.values()) + 1) if ps else 0
    split = int(T * c["baseline_frac"])
    fz = c["feed_zone"]

    def in_feed(v):
        if not fz:
            return False

        # Use the bottom of the cow's bounding box rather than its center.
        # This better captures grazing/feeding when the cow lowers its head.
        x1, y1, x2, y2 = v["box"]
        x = ((x1 + x2) / 2) / W
        bottom_y = y2 / H

        # Small tolerance prevents a cow near the feed-zone boundary
        # from flipping between feeding and another posture because of
        # minor bounding-box movement.
        feed_margin = 0.01
        return (
            fz[0] <= x <= fz[2]
            and (fz[1] - feed_margin) <= bottom_y <= fz[3]
        )

    mounts, iso = detect_mounts(ps, c), _isolation(ps, W, H)
    cows, watchlist, alerts = [], [], []
    for i in sorted(ps):
        d = ps[i]
        href = float(np.percentile([v["h"] for v in d.values()], 90))
        # First classify each second using movement/feed-zone cues.
        # Lying is handled separately below so that a brief bounding-box
        # height drop cannot create a false lying label.
        raw_tl = []
        for s in sorted(d):
            v = d[s]

            if v["speed"] >= c["walk_speed"]:
                st = "walking"
            elif in_feed(v):
                st = "feeding"
            else:
                st = "standing"

            raw_tl.append(dict(
                t=s,
                state=st,
                speed=round(v["speed"], 3),
                x=round(v["cx"] / W, 4),
                y=round(v["cy"] / H, 4)
            ))

        # Require a low-height posture to persist for at least 3 consecutive
        # seconds before calling it lying.
        lying_threshold = c["lying_height_ratio"] * href
        seconds = sorted(d)
        low_height = [
            d[s]["h"] < lying_threshold
            for s in seconds
        ]

        lying_ok = [False] * len(seconds)
        run = 0

        for k, is_low in enumerate(low_height):
            if is_low:
                run += 1
            else:
                run = 0

            if run >= 3:
                lying_ok[k] = True
                lying_ok[k - 1] = True
                lying_ok[k - 2] = True

        tl = []
        for k, item in enumerate(raw_tl):
            st = item["state"]

            # Only use lying when the low-height evidence persists.
            # Feeding/walking still take priority.
            if lying_ok[k] and st == "standing":
                st = "lying"

            tl.append(dict(
                t=item["t"],
                state=st,
                speed=item["speed"],
                x=item["x"],
                y=item["y"]
            ))
        base, rec = [p for p in tl if p["t"] < split], [p for p in tl if p["t"] >= split]
        if len(base) < 2 or len(rec) < 2:
            base = rec = tl
        mb, mr = _metrics(base), _metrics(rec)
        act = (mr["speed"] - mb["speed"]) / max(mb["speed"], 0.05)
        feed = (mr["feeding_pct"] - mb["feeding_pct"]) / mb["feeding_pct"] if mb["feeding_pct"] > 0.05 else 0.0
        lying = mr["lying_pct"] - mb["lying_pct"]
        my = [m for m in mounts if i in (m["upper_id"], m["lower_id"])]
        heat = 0.5 * _c01(len(my) / 2) + 0.3 * _c01(act / 0.5) + 0.2 * _c01(-feed / 0.4)
        health = (0.30 * _c01(-act / 0.4) + 0.25 * _c01(lying / 0.3)
                  + 0.25 * _c01(-feed / 0.5) + 0.20 * _c01(iso[i] / 0.5))
        cows.append(dict(id=i, stats=dict(baseline=mb, recent=mr, isolation_score=round(iso[i], 3),
                                          mount_events=len(my), heat_score=round(heat, 3),
                                          health_score=round(health, 3)), timeline=tl))
        if heat >= c["heat_alert"]:
            r = []
            if my: r.append(f"Mounting seen {len(my)} time(s)")
            if act > 0.2: r.append(f"Activity {min(int(act * 100), 999)}% higher than her own baseline")
            if feed < -0.2: r.append(f"Feeding time down {int(-feed * 100)}% vs her baseline")
            alerts.append(dict(cow_id=i, type="heat", score=round(heat, 2),
                               t=float(my[0]["t_start"] if my else split), reasons=r))
        # Watch case: meaningful behavioural deviation below the formal alert threshold.
        if 0.30 <= health < c["health_alert"]:
            r = []
            if act < -0.10:
                r.append(f"Movement {int(-act * 100)}% lower than her baseline")
            if lying > 0.10:
                r.append(f"Lying time up {int(lying * 100)} percentage points")
            if feed < -0.20:
                r.append(f"Feeding time down {int(-feed * 100)}% vs her baseline")
            if iso[i] > 0.20:
                r.append(f"Away from the herd {int(iso[i] * 100)}% of the time")

            # Only create a Watch case when there is an actual reason.
            if r:
                watchlist.append(dict(
                    cow_id=i,
                    score=round(health, 2),
                    t=float(split),
                    reasons=r
                ))

        if health >= c["health_alert"]:
            r = []
            if act < -0.2: r.append(f"Movement {int(-act * 100)}% lower than her baseline")
            if lying > 0.15: r.append(f"Lying time up {int(lying * 100)} percentage points")
            if feed < -0.2: r.append(f"Feeding time down {int(-feed * 100)}% vs her baseline")
            if iso[i] > 0.2: r.append(f"Away from the herd {int(iso[i] * 100)}% of the time")
            alerts.append(dict(cow_id=i, type="health", score=round(health, 2), t=float(split), reasons=r))
    watchlist.sort(key=lambda a: -a["score"])
    for n, w in enumerate(watchlist, 1):
        w["id"] = f"W{n}"
        w["clip"] = f"clips/watch_cow{w['cow_id']}_{int(w['t'])}.mp4"
        w["clip_start"] = max(0.0, w["t"] - c["clip_pre"])
        w["clip_dur"] = float(c["clip_pre"] + c["clip_post"])

    alerts.sort(key=lambda a: -a["score"])
    for n, a in enumerate(alerts, 1):
        a["id"] = f"A{n}"
        a["clip"] = f"clips/{a['type']}_cow{a['cow_id']}_{int(a['t'])}.mp4"
        a["clip_start"] = max(0.0, a["t"] - c["clip_pre"])
        a["clip_dur"] = float(c["clip_pre"] + c["clip_post"])
    meta = dict(schema_version=1, video_name=video_name, fps=fps, duration_s=T, width=W, height=H,
                baseline_until_s=split, video_start_clock=c["video_start_clock"], processed_video=processed_video)
    return dict(meta=meta, cows=cows, events=mounts, watchlist=watchlist, alerts=alerts)
