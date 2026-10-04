"""Run: python tests/test_pipeline.py   (checks the analysis logic on synthetic cows)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from make_sample_data import build
r = build()
al = {(a["cow_id"], a["type"]) for a in r["alerts"]}
assert (3, "heat") in al, al
assert (5, "health") in al, al
assert not {(1, "heat"), (2, "heat"), (1, "health"), (2, "health"), (4, "heat"), (4, "health")} & al, al
assert len(r["events"]) == 1 and {r["events"][0]["upper_id"], r["events"][0]["lower_id"]} == {3, 4}
print("OK", sorted(al))
