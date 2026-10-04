"""STEP 2 (Person A): check output BEFORE sending to Person B.  python verify_output.py output --expected-cows 5"""
import argparse, json, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("folder")
ap.add_argument("--expected-cows", type=int, default=None)
a = ap.parse_args()
f, bad = Path(a.folder), 0


def say(tag, m):
    global bad
    bad += tag == "FAIL"
    print(tag, m)


if not (f / "results.json").exists():
    print("FAIL results.json missing"); sys.exit(1)
res = json.loads((f / "results.json").read_text(encoding="utf-8"))
for k in ("meta", "cows", "events", "alerts"):
    say("PASS" if k in res else "FAIL", f"key '{k}'")
say("PASS" if (f / "processed_video.mp4").exists() else "FAIL", "processed_video.mp4 exists")
n = len(res.get("cows", []))
say("PASS" if n else "FAIL", f"{n} cows tracked" + ("" if n else " (lower --conf or check video)"))
if a.expected_cows and n > a.expected_cows + 2:
    say("WARN", f"{n} IDs for ~{a.expected_cows} cows: tracker switching IDs, try a clearer clip")
if not res.get("events"):
    say("WARN", "no mounting events (fine if the video has none)")
for al in res.get("alerts", []):
    c = al.get("clip")
    say("PASS" if c and (f / c).exists() else "WARN", f"alert {al['id']} cow {al['cow_id']} {al['type']} score {al['score']} clip {c}")
if not res.get("alerts"):
    say("WARN", "no alerts: tune CFG in analysis.py or pick a clip with a clear story")
print("\nRESULT:", "READY to send to Person B" if bad == 0 else "FIX the FAIL lines first")
sys.exit(1 if bad else 0)
