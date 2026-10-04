"""Run: python tests/test_app_logic.py
Checks the app's data logic on the real verified live results (2 cows, 1 watchlist, 0 alerts, Cow #2 = 0.39).
Works without Streamlit installed."""
import sys, types
from pathlib import Path

try:
    import streamlit  # noqa: F401
except Exception:
    st = types.ModuleType("streamlit"); st.session_state = {}; st.secrets = {}
    sys.modules["streamlit"] = st
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import utils as U

res, folder, label = U.load_results("auto")
assert label == "Live results", label
assert len(res["cows"]) == 2 and len(res["watchlist"]) == 1 and len(res["alerts"]) == 0
w = res["watchlist"][0]
assert w["cow_id"] == 2 and abs(w["score"] - 0.39) < 0.02 and w["kind"] == "watch" and w["type"] == "watch"
assert U.media(folder, w["clip"]), "evidence clip missing"
assert U.media(folder, res["meta"]["processed_video"]), "processed video missing"
rows = {r["cow"]: r for r in U.cow_rows(res)}
assert rows[2]["move_pct"] == -18 and rows[2]["feed_pct"] == -70 and rows[2]["status"] == "watch", rows[2]
assert rows[1]["status"] == "normal"
assert U.status_counts(res) == {"alert": 0, "watch": 1, "normal": 1}
assert 85 <= U.herd_pulse(res) <= 98, U.herd_pulse(res)
ok, checks = U.live_check(); assert ok, checks
for lang in ("en", "hi", "te"):                      # watchlist items must explain in every language (no crash on missing 'type')
    assert U.explain(w, lang, "today 4 PM to 8 PM")[0].strip()
demo, _, dl = U.load_results("demo"); assert dl == "Demo herd" and demo["alerts"]
assert all(set(U.state_shares(c, demo["meta"]["baseline_until_s"])[0]) == set(U.STATE_ORDER) for c in demo["cows"])
print("OK: live =", label, "| pulse", U.herd_pulse(res), "| cow2", rows[2]["move_pct"], "% movement,", rows[2]["feed_pct"], "% feeding")
