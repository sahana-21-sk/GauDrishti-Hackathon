"""STEP 1 (Person A): video -> YOLO -> tracking -> behaviour -> results.json + processed video + clips.
python process_video.py demo.mp4 --out output --feed-zone 0,0.75,1,1"""
import argparse, json, shutil, subprocess
from pathlib import Path
import cv2
import numpy as np
from analysis import build_results

COLORS = {"walking": (0, 165, 255), "feeding": (0, 200, 0), "lying": (255, 120, 0), "standing": (210, 210, 210)}


def run_ffmpeg(args):
    try:
        import imageio_ffmpeg
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", *args], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print("ffmpeg step failed:", e)
        return False


def run_tracking(video, model_name="yolov8n.pt", conf=0.1, imgsz=640):
    from ultralytics import YOLO  # lazy import: tests / sample data don't need it
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    tracks = {}
    stream = YOLO(model_name).track(source=str(video), stream=True, persist=True, tracker="bytetrack.yaml",
                                    classes=[19], conf=conf, iou=0.1, imgsz=imgsz, verbose=False)  # 19 = cow (COCO)
    for fi, r in enumerate(stream):
        rows = []
        if r.boxes is not None and r.boxes.id is not None:
            rows = [(i, *b) for i, b in zip(r.boxes.id.int().cpu().tolist(), r.boxes.xyxy.cpu().tolist())]
        tracks[fi] = rows
    return tracks, fps, W, H


def render_video(src_video, tracks, results, out_path, fps, W, H):
    state = {(c["id"], p["t"]): p["state"] for c in results["cows"] for p in c["timeline"]}
    alert_t = {}
    for a in results["alerts"]:
        alert_t[a["cow_id"]] = min(a["t"], alert_t.get(a["cow_id"], 1e9))

    watch_t = {}
    for w in results.get("watchlist", []):
        watch_t[w["cow_id"]] = min(w["t"], watch_t.get(w["cow_id"], 1e9))

    raw = str(Path(out_path).with_suffix(".raw.mp4"))
    wr = cv2.VideoWriter(raw, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    cap = cv2.VideoCapture(str(src_video)) if src_video else None
    for fi in sorted(tracks):
        if cap is not None:
            ok, frame = cap.read()
            if not ok:
                break
        else:
            frame = np.full((H, W, 3), 40, np.uint8)
        sec = int(fi // fps)
        for (i, x1, y1, x2, y2) in tracks[fi]:
            if (i, sec) not in state:
                continue
            hot = i in alert_t and sec >= alert_t[i]
            watch = i in watch_t and sec >= watch_t[i]

            if hot:
                col = (0, 0, 255)          # Red = formal alert
                label = f"Cow #{i} {state[(i, sec)]} !"
                thickness = 3
            elif watch:
                col = (0, 215, 255)        # Yellow = watch
                label = f"Cow #{i} {state[(i, sec)]} WATCH"
                thickness = 3
            else:
                col = COLORS[state[(i, sec)]]
                label = f"Cow #{i} {state[(i, sec)]}"
                thickness = 2

            cv2.rectangle(
                frame,
                (int(x1), int(y1)),
                (int(x2), int(y2)),
                col,
                thickness
            )

            cv2.putText(
                frame,
                label,
                (int(x1), max(15, int(y1) - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                col,
                2
            )
        wr.write(frame)
    wr.release()
    if cap is not None:
        cap.release()
    vf = ["-vf", "scale=-2:540"] if H > 540 else []
    if not run_ffmpeg(["-i", raw, *vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
                       "-crf", "26", "-an", str(out_path)]):
        shutil.copy(raw, out_path)
    Path(raw).unlink(missing_ok=True)


def make_clips(processed, results, out_dir):
    # Formal alerts
    for a in results["alerts"]:
        dst = Path(out_dir) / a["clip"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not run_ffmpeg(["-ss", str(a["clip_start"]), "-i", str(processed), "-t", str(a["clip_dur"]),
                           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(dst)]):
            a["clip"] = None

    # Watchlist evidence clips
    for w in results.get("watchlist", []):
        dst = Path(out_dir) / w["clip"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not run_ffmpeg(["-ss", str(w["clip_start"]), "-i", str(processed), "-t", str(w["clip_dur"]),
                           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(dst)]):
            w["clip"] = None


def process(video, out_dir, model="yolov8n.pt", conf=0.3, feed_zone=None, start_clock="06:00"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tracks, fps, W, H = run_tracking(video, model, conf)
    cfg = dict(video_start_clock=start_clock)
    if feed_zone:
        cfg["feed_zone"] = feed_zone
    res = build_results(tracks, fps, W, H, cfg, video_name=Path(video).name)
    render_video(video, tracks, res, out / "processed_video.mp4", fps, W, H)
    make_clips(out / "processed_video.mp4", res, out)
    (out / "results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"Done. cows={len(res['cows'])} events={len(res['events'])} alerts={len(res['alerts'])}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default="output")
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--conf", type=float, default=0.1)
    ap.add_argument("--feed-zone", default=None, help="x1,y1,x2,y2 fractions, e.g. 0,0.75,1,1")
    ap.add_argument("--start-clock", default="06:00")
    a = ap.parse_args()
    fz = tuple(float(v) for v in a.feed_zone.split(",")) if a.feed_zone else None
    process(a.video, a.out, a.model, a.conf, fz, a.start_clock)
