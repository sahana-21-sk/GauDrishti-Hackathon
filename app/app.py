"""Gaudrishti dashboard.  Reads results.json only (the CV pipeline runs once, in Colab or on a laptop).
The UI adapts to the frozen backend. Every page is wrapped in safe(), so one failure never takes the app down."""
import sys, html, json, time, tempfile, datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import utils as U

st.set_page_config(page_title="Gaudrishti", page_icon="🐄", layout="wide", initial_sidebar_state="expanded")

# ====================================================================== STYLE (big, clear, consistent)
st.markdown("""<style>
html{font-size:18px}
.block-container{padding-top:1.2rem;max-width:1450px}
h1{font-size:2.3rem!important} h2{font-size:1.85rem!important} h3{font-size:1.5rem!important}
.stMarkdown p,.stMarkdown li,label,.stCaption,.stAlert{font-size:1.02rem}
footer{visibility:hidden}
/* ---- sidebar ---- */
section[data-testid="stSidebar"]{background:#EEF4FF;border-right:2px solid #C7D8F5;width:350px!important;min-width:350px!important}
section[data-testid="stSidebar"] *{font-size:1.02rem}
.sb-brand{background:linear-gradient(135deg,#0F5132,#198754);color:#fff;border-radius:18px;padding:16px 18px;margin-bottom:6px}
.sb-brand .n{font-size:1.7rem;font-weight:800;line-height:1.1;color:#fff}
.sb-brand .t{font-size:.95rem;opacity:.92;color:#fff}
.sb-title{font-size:.85rem!important;font-weight:800;letter-spacing:.14em;color:#1D4ED8;margin:20px 0 8px;border-bottom:2px solid #C7D8F5;padding-bottom:4px}
section[data-testid="stSidebar"] div[role="radiogroup"]{gap:7px}
section[data-testid="stSidebar"] div[role="radiogroup"] label{background:#fff;border:2px solid #C7D8F5;border-radius:14px;padding:12px 15px;width:100%;font-weight:800;margin:0;transition:all .15s ease}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover{background:#E0ECFF;border-color:#93B4F3;transform:translateX(2px)}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){background:#2563EB;border-color:#2563EB;box-shadow:0 5px 14px rgba(37,99,235,.20)}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) *{color:#fff!important}
.srcbadge{background:#fff;border:2px solid #2563EB;color:#1D4ED8;border-radius:999px;padding:6px 14px;font-weight:800;display:inline-block;margin-top:6px}
.snap{background:#fff;border:2px solid #CFE8D8;border-radius:14px;padding:10px 14px}
.snap div{display:flex;justify-content:space-between;font-size:1.05rem;padding:3px 0}
.snap b{color:#0F5132;font-size:1.15rem}
/* ---- hero + cards ---- */
.hero{background:linear-gradient(120deg,#0F5132,#198754 60%,#7BC47F);color:#fff;padding:26px 32px;border-radius:20px;margin-bottom:18px}
.hero h1{margin:0;color:#fff;font-size:2.5rem!important} .hero p{margin:6px 0 0;font-size:1.15rem;opacity:.96;color:#fff}
.watch-hero{background:linear-gradient(120deg,#B45309,#F59E0B 60%,#FCD34D)}
.kpi{background:#fff;border:2px solid #DDEBE1;border-radius:18px;padding:16px 20px;box-shadow:0 4px 14px rgba(15,81,50,.08);height:100%}
.kpi .l{font-size:.85rem;font-weight:800;color:#4B5F55;text-transform:uppercase;letter-spacing:.07em}
.kpi .v{font-size:3rem;font-weight:800;line-height:1.1;color:#0F5132}
.kpi .s{font-size:.95rem;color:#5B6B63}
.kpi.red .v{color:#DC2626}.kpi.amber .v{color:#D97706}
.pill{display:inline-block;padding:4px 14px;border-radius:999px;font-size:.9rem;font-weight:800;margin:0 8px 6px 0}
.red{background:#FDE2E2;color:#B42318}.amber{background:#FEF0C7;color:#B54708}.green{background:#D1FADF;color:#05603A}.blue{background:#D1E9FF;color:#175CD3}.grey{background:#EEF2F0;color:#3B4A43}
.item{border-left:10px solid;border-radius:14px;background:#fff;padding:12px 18px;margin-bottom:8px;box-shadow:0 2px 10px rgba(15,81,50,.08)}
.item.alert{border-color:#DC2626}.item.watch{border-color:#F59E0B}
.item h3{margin:0 0 4px 0;color:#0F3D2A}
.why li{font-size:1.08rem;margin-bottom:4px}
.explain{background:#F4FAF6;border:2px solid #CFE8D8;border-radius:12px;padding:12px 16px;font-size:1.08rem;line-height:1.55;margin:6px 0}
.sec{font-size:1.5rem;font-weight:800;color:#0F3D2A;margin:10px 0 2px}
.legend span{display:inline-block;margin:0 14px 6px 0;font-size:1rem;font-weight:600}
.legend i{display:inline-block;width:14px;height:14px;border-radius:4px;margin-right:6px;vertical-align:-2px}
.flow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:6px 0 10px}
.flow .n{background:#0F5132;color:#fff;border-radius:10px;padding:6px 14px;font-weight:700;font-size:.98rem}
.flow .a{color:#198754;font-weight:900;font-size:1.2rem}
div[data-testid="stDataFrame"]{font-size:1.05rem}
</style>""", unsafe_allow_html=True)

NAV = ["📊 Overview", "📤 Upload & Analyze", "🚨 Alerts & Watchlist", "🟡 Watchlist", "🐄 Cow Health Cards", "🗺️ Herd Map", "🎥 CCTV & Evidence", "ℹ️ About & Method"]


# ====================================================================== small helpers
def safe(fn):
    try:
        fn()
    except Exception as e:
        st.warning(f"This section could not load ({type(e).__name__}: {e}). The rest of the app still works.")


def pill(txt, cls):
    return f'<span class="pill {cls}">{html.escape(str(txt))}</span>'


def kpi(label, value, sub="", tone=""):
    return f'<div class="kpi {tone}"><div class="l">{label}</div><div class="v">{value}</div><div class="s">{sub}</div></div>'


def style(fig, title, h=400):
    fig.update_layout(title=dict(text=title, font=dict(size=22, color="#0F3D2A"), x=0.0, xanchor="left"),
                      font=dict(size=16, color="#1B1B1B"), height=h, margin=dict(l=20, r=20, t=80, b=50),
                      paper_bgcolor="white", plot_bgcolor="#F7FBF8", hoverlabel=dict(font_size=16),
                      legend=dict(font=dict(size=15), orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_xaxes(gridcolor="#E3EEE7", tickfont=dict(size=15), title_font=dict(size=16))
    fig.update_yaxes(gridcolor="#E3EEE7", tickfont=dict(size=15), title_font=dict(size=16))
    return fig


def chart(fig, key):
    st.plotly_chart(fig, width="stretch", key=key)


def video(path, caption=None):
    if path:
        st.video(path)
        if caption:
            st.caption(caption)
    else:
        st.info("Video not available here. Everything else on this page still works.")


# ====================================================================== state hooks (must run BEFORE the widgets below)
if st.session_state.pop("_goto_mine", False):
    st.session_state["src"], st.session_state["nav"] = "My analysis", NAV[0]
has_mine = "analysis" in st.session_state
SRC = ["Auto (live results, else demo)", "Demo herd"] + (["My analysis"] if has_mine else [])
if st.session_state.get("src") not in SRC:
    st.session_state["src"] = SRC[0]
if st.session_state.get("nav") not in NAV:
    st.session_state["nav"] = NAV[0]

# ====================================================================== SIDEBAR
sb = st.sidebar
sb.markdown('<div class="sb-brand"><div class="n">🐄 Gaudrishti</div><div class="t">Giving the silent herd a voice</div></div>', unsafe_allow_html=True)
sb.markdown('<div class="sb-title">1 · GO TO</div>', unsafe_allow_html=True)
page = sb.radio("Go to", NAV, key="nav", label_visibility="collapsed")

sb.markdown('<div class="sb-title">2 · DATA SOURCE</div>', unsafe_allow_html=True)
src = sb.radio("Data source", SRC, key="src", label_visibility="collapsed")
res, folder, mode = U.load_results({SRC[0]: "auto", SRC[1]: "demo"}.get(src, "mine"))
if res is None:
    st.error("No results found. Add data/live/results.json or data/demo/results.json, or upload a video in the Analyze page.")
    st.stop()
sb.markdown(f'<div class="srcbadge">● Showing: {mode}</div>', unsafe_allow_html=True)
if has_mine and sb.button("Clear my analysis"):
    st.session_state.pop("analysis", None)
    st.rerun()

sb.markdown('<div class="sb-title">3 · SETTINGS</div>', unsafe_allow_html=True)
lang_label = sb.radio(
    "Explanation language",
    list(U.LANGS),
    key="lang",
)
lang = U.LANGS[lang_label]
sb.caption(f"✓ Explanations and voice: {lang_label}")
clock = str(res["meta"].get("video_start_clock", "06:00"))
try:
    hh, mm = (int(x) for x in clock.split(":")[:2])
except Exception:
    hh, mm = 6, 0
seen_at = sb.time_input("Time heat was first seen", dt.time(hh, mm), key=f"seen_{mode}_{clock}")
window = U.breeding_window(seen_at.hour)

cows = {c["id"]: c for c in res["cows"]}
meta = res["meta"]
split = meta.get("baseline_until_s", 0)
counts = U.status_counts(res)
pulse = U.herd_pulse(res)
sb.markdown('<div class="sb-title">4 · HERD SNAPSHOT</div>', unsafe_allow_html=True)
sb.markdown(f'<div class="snap"><div><span>Herd Pulse</span><b>{pulse}/100</b></div><div><span>Cows tracked</span><b>{len(cows)}</b></div>'
            f'<div><span>🔴 Alerts</span><b>{len(res["alerts"])}</b></div><div><span>🟡 Watchlist</span><b>{len(res["watchlist"])}</b></div>'
            f'<div><span>🟢 Normal cows</span><b>{counts["normal"]}</b></div></div>', unsafe_allow_html=True)
sb.caption("Screening tool, not a diagnosis. A vet confirms.")


# ====================================================================== shared UI pieces
def explain_block(x, uid):
    k = f"{uid}_{lang}"
    if st.button(f"💬 Explain in {lang_label.split(' ')[0]}", key=f"ex_{k}"):
        st.session_state[f"show_{k}"] = True
    if st.session_state.get(f"show_{k}"):
        with st.spinner("Writing the explanation..."):
            text, srcname = U.explain(x, lang, window)
        st.markdown(f'<div class="explain">{html.escape(text).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
        st.caption("Written by Gemini" if srcname == "gemini" else "Template text (Gemini not connected)")
        if st.button("🔊 Speak this", key=f"sp_{k}"):
            audio = U.speak(text, lang, x["id"], srcname == "template")
            if audio:
                st.audio(audio, format="audio/mp3")
            else:
                st.info("Audio is not available right now. The text above has the message.")


def kind_text(x):
    return {"heat": "Possible heat", "health": "Possible health issue"}.get(x.get("type"), "Watch: mild change")


def item_card(x, uid, full=True):
    kind = x["kind"]
    tag = ("ALERT", "red") if kind == "alert" else ("WATCHLIST", "amber")
    st.markdown(f'<div class="item {kind}"><h3>Cow #{x["cow_id"]}</h3>{pill(tag[0], tag[1])}{pill(kind_text(x), "blue")}'
                f'{pill(str(int(x["score"] * 100)) + "% deviation", "grey")}</div>', unsafe_allow_html=True)
    st.progress(min(max(float(x["score"]), 0.0), 1.0))
    st.markdown('<ul class="why">' + "".join(f"<li>{html.escape(r)}</li>" for r in x["reasons"]) + "</ul>", unsafe_allow_html=True)
    if not full:
        return
    if x.get("type") == "heat":
        st.info(f"Breeding Time Advisor: best window **{window}**. Call the vet.")
    explain_block(x, uid)


# ====================================================================== PAGE 1: OVERVIEW
def overview():
    st.markdown(f'<div class="hero"><h1>🐄 Gaudrishti Herd Overview</h1><p>{html.escape(str(meta.get("video_name", "")))} · '
                f'{int(meta.get("duration_s", 0))} s of footage · baseline = first {int(split)} s (each cow\'s own normal)</p></div>',
                unsafe_allow_html=True)
    tone = "red" if res["alerts"] else "amber" if res["watchlist"] else ""
    k = st.columns(5, gap="medium")
    k[0].markdown(kpi("Herd Pulse", f"{pulse}<span style='font-size:1.3rem'>/100</span>", "100 = everyone normal"), unsafe_allow_html=True)
    k[1].markdown(kpi("Cows tracked", len(cows), "stable IDs"), unsafe_allow_html=True)
    k[2].markdown(kpi("Alerts", len(res["alerts"]), "act today" if res["alerts"] else "none", "red" if res["alerts"] else ""), unsafe_allow_html=True)
    k[3].markdown(kpi("Watchlist", len(res["watchlist"]), "keep an eye" if res["watchlist"] else "none", "amber" if res["watchlist"] else ""), unsafe_allow_html=True)
    k[4].markdown(kpi("Mounting events", len(res["events"]), "heat sign"), unsafe_allow_html=True)
    st.write("")

    l, r = st.columns([3, 2], gap="large")
    with l:
        st.markdown('<div class="sec">Processed CCTV video</div>', unsafe_allow_html=True)
        video(U.media(folder, meta.get("processed_video")), "Boxes: orange walking · green feeding · blue lying · grey standing · yellow WATCH · red ALERT")
    with r:
        st.markdown('<div class="sec">Needs attention first</div>', unsafe_allow_html=True)
        top = sorted(U.all_items(res), key=lambda x: -x["score"])[:3]
        if not top:
            st.success("✅ No alerts and nobody on the watchlist. The herd looks normal.")
        for x in top:
            with st.container(border=True):
                item_card(x, f"ov{x['id']}", full=False)
        if top:
            st.caption("Open **🚨 Alerts & Watchlist** for evidence clips, explanations and voice.")

    st.markdown('<div class="sec">Herd status table</div>', unsafe_allow_html=True)
    rows = U.cow_rows(res)
    df = pd.DataFrame([{"Cow": f"#{r['cow']}", "Status": r["label"], "Health deviation (%)": r["health"], "Heat score (%)": r["heat"],
                        "Movement vs normal (%)": r["move_pct"], "Feeding vs normal (%)": r["feed_pct"], "Lying change (pts)": r["lying_pts"],
                        "Away from herd (%)": r["isolation"], "Mounts": r["mounts"]} for r in rows])
    st.dataframe(df, hide_index=True, width="stretch", column_config={
        "Health deviation (%)": st.column_config.ProgressColumn("Health deviation (%)", min_value=0, max_value=100, format="%d"),
        "Heat score (%)": st.column_config.ProgressColumn("Heat score (%)", min_value=0, max_value=100, format="%d")})
    d1, d2 = st.columns(2)
    d1.download_button("⬇ Download herd table (CSV)", df.to_csv(index=False).encode("utf-8"), "gaudrishti_herd.csv", "text/csv")
    d2.download_button("⬇ Download results.json", json.dumps(res, indent=2).encode("utf-8"), "results.json", "application/json")

    a, b = st.columns([3, 2], gap="large")
    th = U.thresholds()
    with a:
        names = [f"Cow #{r['cow']}" for r in rows]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=names, y=[r["health"] for r in rows], name="Health deviation", marker_color="#2563EB",
                             text=[f"{r['health']}%" for r in rows], textposition="outside", textfont=dict(size=16)))
        fig.add_trace(go.Bar(x=names, y=[r["heat"] for r in rows], name="Heat score", marker_color="#E11D8F",
                             text=[f"{r['heat']}%" for r in rows], textposition="outside", textfont=dict(size=16)))
        for y, txt, col in ((th["watch_from"] * 100, f"Watchlist from {int(th['watch_from'] * 100)}%", "#D97706"), (th["health_alert"] * 100, f"Health alert {int(th['health_alert'] * 100)}%", "#DC2626"),
                            (th["heat_alert"] * 100, f"Heat alert {int(th['heat_alert'] * 100)}%", "#9D174D")):
            fig.add_hline(y=y, line_dash="dash", line_color=col, line_width=2, annotation_text=txt, annotation_position="top left",
                          annotation_font=dict(size=14, color=col))
        fig.update_layout(barmode="group", bargap=0.35)
        fig.update_yaxes(range=[0, 100], title="Score (%)")
        chart(style(fig, "Behaviour change vs each cow's own normal", 440), "ov_scores")
    with b:
        order = ["alert", "watch", "normal"]
        fig = go.Figure(go.Pie(labels=[U.STATUS_LABEL[o].title() for o in order], values=[counts[o] for o in order], hole=0.62,
                               marker=dict(colors=[U.STATUS_COLORS[o] for o in order]), textinfo="value", textfont=dict(size=22),
                               sort=False, direction="clockwise"))
        fig.update_layout(annotations=[dict(text=f"<b>{len(cows)}</b><br>cows", x=0.5, y=0.5, font=dict(size=24), showarrow=False)],
                          legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center", font=dict(size=16)))
        chart(style(fig, "Herd status", 440), "ov_donut")


# ====================================================================== PAGE 2: ALERTS & WATCHLIST
def alerts_page():
    st.markdown('<div class="sec">Alerts & Watchlist</div>', unsafe_allow_html=True)
    st.caption("ALERT = strong change from her own normal. WATCHLIST = mild drift: keep an eye on her, no action needed yet.")
    f1, f2, f3 = st.columns([2, 2, 2], gap="large")
    show = f1.multiselect("Show", ["Alerts", "Watchlist"], default=["Alerts", "Watchlist"], key="f_show")
    mn = f2.slider("Minimum deviation (%)", 0, 100, 0, key="f_min")
    sort = f3.selectbox("Sort by", ["Highest deviation", "Cow number", "Time in video"], key="f_sort")
    items = [x for x in U.all_items(res) if int(x["score"] * 100) >= mn and (("Alerts" in show and x["kind"] == "alert") or ("Watchlist" in show and x["kind"] == "watch"))]
    items.sort(key={"Highest deviation": lambda x: -x["score"], "Cow number": lambda x: x["cow_id"], "Time in video": lambda x: x.get("t", 0)}[sort])
    if not items:
        st.success("✅ Nothing to show with these filters." if U.all_items(res) else "✅ No alerts and nobody on the watchlist. The herd looks normal.")
    for x in items:
        with st.container(border=True):
            l, r = st.columns([3, 2], gap="large")
            with l:
                item_card(x, f"al{x['id']}", full=False)
                clip = U.media(folder, x.get("clip"))
                st.markdown("**Evidence clip**")
                video(clip) if clip else st.caption("Evidence clip not available.")
            with r:
                st.markdown(f"**When:** {x.get('t', 0):.0f} s into the video")
                if x.get("type") == "heat":
                    st.info(f"Breeding Time Advisor: best window **{window}**. Call the vet.")
                explain_block(x, f"al{x['id']}")


# ====================================================================== PAGE 4: WATCHLIST
def watchlist_page():
    st.markdown(
        '<div class="hero watch-hero"><h1>🟡 Behaviour Watchlist</h1>'
        '<p>Meaningful behavioural changes that need attention, but have not crossed the formal alert threshold.</p></div>',
        unsafe_allow_html=True,
    )
    items = [dict(x, kind="watch") for x in res.get("watchlist", [])]
    if not items:
        st.success("✅ No cows are currently on the behavioural watchlist.")
        return
    for n, x in enumerate(sorted(items, key=lambda q: -q["score"]), 1):
        with st.container(border=True):
            item_card(x, f"wl{n}_{x['cow_id']}", full=True)

# ====================================================================== PAGE 3: COW HEALTH CARDS
def health_cards():
    ids = list(cows)
    if st.session_state.get("cow_pick") not in ids:
        st.session_state["cow_pick"] = ids[0]
    fmt = lambda i: f"{U.STATUS_ICON[U.cow_status(res, i)]} Cow #{i}"
    cid = st.radio("Choose a cow", ids, format_func=fmt, horizontal=True, key="cow_pick") if len(ids) <= 8 else \
        st.selectbox("Choose a cow", ids, format_func=fmt, key="cow_pick")
    c, s = cows[cid], cows[cid]["stats"]
    status = U.cow_status(res, cid)
    mine = [x for x in U.all_items(res) if x["cow_id"] == cid]
    b, r = s["baseline"], s["recent"]
    cls = {"alert": "red", "watch": "amber", "normal": "green"}[status]
    st.markdown(f'<div class="hero"><h1>Cow #{cid} Health Card</h1><p>{pill(U.STATUS_LABEL[status], cls)} '
                f'seen for {len(c["timeline"])} s · compared only with her own baseline</p></div>', unsafe_allow_html=True)

    th = U.thresholds()
    g1, g2 = st.columns(2, gap="large")
    for col, val, name, steps, key in (
            (g1, s.get("health_score", 0), "Health deviation", [(0, th["watch_from"], "#BBF7D0"), (th["watch_from"], th["health_alert"], "#FDE68A"), (th["health_alert"], 1, "#FECACA")], "g_h"),
            (g2, s.get("heat_score", 0), "Signs of heat", [(0, th["heat_alert"], "#BBF7D0"), (th["heat_alert"], 1, "#FECACA")], "g_t")):
        fig = go.Figure(go.Indicator(mode="gauge+number", value=round(val * 100), number=dict(suffix="%", font=dict(size=46)),
                                     gauge=dict(axis=dict(range=[0, 100], tickfont=dict(size=15)), bar=dict(color="#0F5132"),
                                                steps=[dict(range=[a * 100, z * 100], color=c_) for a, z, c_ in steps])))
        fig.update_layout(height=270, margin=dict(l=30, r=30, t=70, b=10), font=dict(size=16),
                          title=dict(text=name, font=dict(size=22, color="#0F3D2A"), x=0.5, xanchor="center"), paper_bgcolor="white")
        with col:
            chart(fig, f"{key}_{cid}")

    m = st.columns(5, gap="medium")
    mv = U.pct_change(r["speed"], b["speed"])
    fd = U.pct_change(r["feeding_pct"], b["feeding_pct"])
    m[0].markdown(kpi("Movement", f"{r['speed']}", f"{mv:+.0f}% vs normal"), unsafe_allow_html=True)
    m[1].markdown(kpi("Feeding time", f"{int(r['feeding_pct'] * 100)}%", f"{fd:+.0f}% vs normal"), unsafe_allow_html=True)
    m[2].markdown(kpi("Lying time", f"{int(r['lying_pct'] * 100)}%", f"{int((r['lying_pct'] - b['lying_pct']) * 100):+d} pts vs normal"), unsafe_allow_html=True)
    m[3].markdown(kpi("Away from herd", f"{int(s.get('isolation_score', 0) * 100)}%", "of the time"), unsafe_allow_html=True)
    m[4].markdown(kpi("Mounting", s.get("mount_events", 0), "events"), unsafe_allow_html=True)

    if mine:
        st.markdown('<div class="sec">Why she is flagged</div>', unsafe_allow_html=True)
        for x in mine:
            with st.container(border=True):
                item_card(x, f"hc{x['id']}")
                clip = U.media(folder, x.get("clip"))
                if clip:
                    with st.expander("▶ Evidence clip"):
                        video(clip)
    else:
        st.success("✅ Nothing unusual compared with her own normal.")

    # --- chart 1: baseline vs recent
    fig = make_subplots(rows=1, cols=3, subplot_titles=("Movement (body-lengths / s)", "Lying time (%)", "Feeding time (%)"), horizontal_spacing=0.09)
    vals = [(b["speed"], r["speed"]), (b["lying_pct"] * 100, r["lying_pct"] * 100), (b["feeding_pct"] * 100, r["feeding_pct"] * 100)]
    for i, (vb, vr) in enumerate(vals, 1):
        fig.add_trace(go.Bar(x=["Her normal"], y=[vb], name="Her normal (baseline)", marker_color="#9DB8A7", showlegend=(i == 1),
                             text=[f"{vb:.2f}" if i == 1 else f"{vb:.0f}%"], textposition="outside", textfont=dict(size=16)), row=1, col=i)
        fig.add_trace(go.Bar(x=["Now"], y=[vr], name="Now (recent)", marker_color="#0F5132", showlegend=(i == 1),
                             text=[f"{vr:.2f}" if i == 1 else f"{vr:.0f}%"], textposition="outside", textfont=dict(size=16)), row=1, col=i)
    fig.update_layout(bargap=0.3)
    fig.update_annotations(font_size=17)
    chart(style(fig, "Her normal vs now", 420), f"c_bar_{cid}")

    # --- chart 2: behaviour strip
    tl = c["timeline"]
    fig = go.Figure()
    for stt in U.STATE_ORDER:
        pts = [p for p in tl if p["state"] == stt]
        fig.add_trace(go.Bar(x=[p["t"] + 0.5 for p in pts], y=[1] * len(pts), width=1, name=stt.title(), marker_color=U.STATE_COLORS[stt],
                             hovertemplate=f"{stt.title()}<br>second %{{x:.0f}}<extra></extra>"))
    fig.add_vrect(x0=0, x1=split, fillcolor="#E8F5EE", opacity=0.35, line_width=0, layer="below")
    fig.add_vline(x=split, line_dash="dash", line_color="#0F3D2A", line_width=2, annotation_text="baseline ends", annotation_font=dict(size=15))
    fig.update_layout(barmode="stack", bargap=0)
    fig.update_yaxes(visible=False, range=[0, 1])
    fig.update_xaxes(title="Seconds into the video")
    chart(style(fig, "What she did, second by second", 300), f"c_strip_{cid}")

    # --- chart 3: speed
    fig = go.Figure(go.Scatter(x=[p["t"] for p in tl], y=[p["speed"] for p in tl], mode="lines+markers", name="Movement",
                               line=dict(color="#0F5132", width=3), marker=dict(size=9)))
    fig.add_hline(y=b["speed"], line_dash="dash", line_color="#6B8F7A", annotation_text="her normal", annotation_font=dict(size=14))
    fig.add_hline(y=r["speed"], line_dash="dot", line_color="#DC2626", annotation_text="now (average)", annotation_position="bottom right", annotation_font=dict(size=14))
    fig.add_vline(x=split, line_dash="dash", line_color="#0F3D2A", line_width=1)
    fig.update_xaxes(title="Seconds into the video")
    fig.update_yaxes(title="Movement (body-lengths / s)", rangemode="tozero")
    chart(style(fig, "Movement over time", 360), f"c_spd_{cid}")

    # --- chart 4: where her time went
    sb_, sr_ = U.state_shares(c, split)
    fig = go.Figure()
    for stt in U.STATE_ORDER:
        fig.add_trace(go.Bar(y=["Her normal", "Now"], x=[sb_[stt], sr_[stt]], name=stt.title(), orientation="h", marker_color=U.STATE_COLORS[stt],
                             text=[f"{sb_[stt]}%" if sb_[stt] else "", f"{sr_[stt]}%" if sr_[stt] else ""], textposition="inside", textfont=dict(size=16, color="white")))
    fig.update_layout(barmode="stack")
    fig.update_xaxes(title="% of her time", range=[0, 100])
    chart(style(fig, "Where her time went", 300), f"c_share_{cid}")


# ====================================================================== PAGE 4: HERD MAP
def herd_map():
    st.markdown('<div class="sec">Herd map</div>', unsafe_allow_html=True)
    st.caption("Press ▶ Play or drag the time slider under the map. Colour = cow status. Hover a cow for details.")
    times = sorted({p["t"] for c in res["cows"] for p in c["timeline"]})
    if not times:
        st.info("No position data in these results.")
        return
    status = {i: U.cow_status(res, i) for i in cows}
    bg = st.toggle("Show the camera view behind the cows", value=False, key="map_bg")

    def frame_trace(t):
        xs, ys, txt, col, hov = [], [], [], [], []
        for c in res["cows"]:
            p = next((q for q in c["timeline"] if q["t"] == t), None)
            if p:
                xs.append(p["x"]); ys.append(1 - p["y"]); txt.append(f"#{c['id']}"); col.append(U.STATUS_COLORS[status[c["id"]]])
                hov.append(f"Cow #{c['id']}<br>{p['state']}<br>speed {p['speed']}<br>{U.STATUS_LABEL[status[c['id']]].title()}")
        return go.Scatter(x=xs, y=ys, mode="markers+text", text=txt, textposition="top center", textfont=dict(size=17, color="#0F3D2A"),
                          marker=dict(size=32, color=col, line=dict(width=3, color="white")), hovertext=hov, hoverinfo="text", showlegend=False)

    fig = go.Figure(data=[frame_trace(times[0])] + [go.Scatter(x=[None], y=[None], mode="markers", name=U.STATUS_LABEL[k].title(),
                                                                  marker=dict(size=16, color=U.STATUS_COLORS[k])) for k in ("alert", "watch", "normal")],
                    frames=[go.Frame(data=[frame_trace(t)], traces=[0], name=str(t)) for t in times])
    fig.update_layout(
        updatemenus=[dict(type="buttons", showactive=False, x=0, y=-0.09, xanchor="left", yanchor="top", pad=dict(t=10), buttons=[
            dict(label="▶ Play", method="animate", args=[None, dict(frame=dict(duration=800, redraw=True), fromcurrent=True, transition=dict(duration=300))]),
            dict(label="⏸ Pause", method="animate", args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate", transition=dict(duration=0))])])],
        sliders=[dict(active=0, x=0.2, len=0.8, y=-0.09, yanchor="top", currentvalue=dict(prefix="Time: ", suffix=" s", font=dict(size=18)),
                      steps=[dict(method="animate", label=str(t), args=[[str(t)], dict(mode="immediate", frame=dict(duration=0, redraw=True), transition=dict(duration=0))]) for t in times])])
    fig.update_xaxes(range=[0, 1], showticklabels=False, title="Left of the camera view  →  right")
    fig.update_yaxes(range=[0, 1], showticklabels=False, title="Bottom  →  top of the view")
    if bg:
        b64 = U.frame_jpeg_b64(U.media(folder, meta.get("processed_video")) or "", 0.0)
        if b64:
            fig.update_layout(images=[dict(source="data:image/jpeg;base64," + b64, xref="x", yref="y", x=0, y=1, sizex=1, sizey=1,
                                           sizing="stretch", opacity=0.6, layer="below")])
        else:
            st.caption("Camera view not available for this video.")
    style(fig, "Where each cow is", 680)
    fig.update_layout(margin=dict(l=20, r=20, t=80, b=140))
    chart(fig, "map_anim")

    pal = ["#0F5132", "#2563EB", "#E11D8F", "#D97706", "#7C3AED", "#0891B2", "#65A30D", "#B91C1C"]
    fig = go.Figure()
    for n, c in enumerate(res["cows"]):
        col = pal[n % len(pal)]
        xs, ys = [p["x"] for p in c["timeline"]], [1 - p["y"] for p in c["timeline"]]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=f"Cow #{c['id']}", line=dict(color=col, width=3), marker=dict(size=7, color=col)))
        fig.add_trace(go.Scatter(x=xs[:1], y=ys[:1], mode="markers+text", text=["start"], textposition="bottom center", showlegend=False,
                                 marker=dict(size=18, color=col, symbol="circle", line=dict(width=2, color="white"))))
        fig.add_trace(go.Scatter(x=xs[-1:], y=ys[-1:], mode="markers+text", text=["end"], textposition="top center", showlegend=False,
                                 marker=dict(size=18, color=col, symbol="diamond", line=dict(width=2, color="white"))))
    fig.update_xaxes(range=[0, 1], showticklabels=False, title="Left of the camera view  →  right")
    fig.update_yaxes(range=[0, 1], showticklabels=False, title="Bottom  →  top of the view")
    chart(style(fig, "Movement trails (○ start, ◇ end)", 480), "map_trails")


# ====================================================================== PAGE 5: CCTV & EVIDENCE
def evidence():
    st.markdown('<div class="sec">CCTV & evidence</div>', unsafe_allow_html=True)
    video(U.media(folder, meta.get("processed_video")))
    st.markdown('<div class="legend">' + "".join(f'<span><i style="background:{c}"></i>{t}</span>' for t, c in (
        ("Walking", "#F59E0B"), ("Feeding", "#16A34A"), ("Lying", "#2563EB"), ("Standing", "#9CA3AF"), ("WATCH", "#FACC15"), ("ALERT", "#DC2626"))) + "</div>", unsafe_allow_html=True)
    ev = res.get("events", [])
    st.markdown('<div class="sec">Mounting events</div>', unsafe_allow_html=True)
    if ev:
        st.dataframe(pd.DataFrame([dict(Start=f"{e['t_start']} s", End=f"{e['t_end']} s", Upper=f"Cow #{e['upper_id']}", Lower=f"Cow #{e['lower_id']}") for e in ev]),
                     hide_index=True, width="stretch")
    else:
        st.info("No mounting events in this footage.")
    st.markdown('<div class="sec">Evidence clips</div>', unsafe_allow_html=True)
    clips = [(x, U.media(folder, x.get("clip"))) for x in U.all_items(res)]
    clips = [(x, p) for x, p in clips if p]
    if not clips:
        st.info("No evidence clips for this footage.")
    cols = st.columns(2, gap="large")
    for n, (x, p) in enumerate(clips):
        with cols[n % 2]:
            with st.container(border=True):
                st.markdown(f"**{x['id']} · Cow #{x['cow_id']} · {kind_text(x)} · {int(x['score'] * 100)}%**")
                st.video(p)
                st.caption("; ".join(x["reasons"]))


# ====================================================================== PAGE 6: ANALYZE A VIDEO
def analyze():
    st.markdown('<div class="hero"><h1>📤 Upload & Analyze</h1><p>Upload cattle CCTV footage and run the existing YOLO + ByteTrack + behaviour pipeline.</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="flow">' + '<span class="a">→</span>'.join(f'<span class="n">{t}</span>' for t in (
        "Video", "YOLO", "ByteTrack", "Behaviour", "Own baseline", "Watchlist / alerts", "Evidence", "Gemini", "Voice")) + "</div>", unsafe_allow_html=True)
    live_ok = U.engine_available()
    opts = ["Upload a video (AI runs here)", "Load Colab results (output.zip)"]
    way = st.radio("How do you want to add data?", opts, horizontal=True, index=0 if live_ok else 1, key="way")
    if way == opts[1]:
        z = st.file_uploader("output.zip from the Colab notebook", type=["zip"], key="zipup")
        if z and st.button("Load results", type="primary", key="loadzip"):
            try:
                st.session_state["analysis"] = U.load_zip_results(z.getvalue())
                st.session_state["_goto_mine"] = True
                st.rerun()
            except Exception as e:
                st.error(f"Could not load this zip: {e}")
        return
    if not live_ok:
        st.warning("The live AI engine (YOLO) is not installed in this deployment, so video processing is off here. "
                   "Run the app on your laptop (`pip install -r requirements-local.txt`) or process in Colab and use 'Load Colab results'.")
        return
    up = st.file_uploader("Cattle CCTV / farm video (MP4, MOV, AVI, MKV)", type=["mp4", "mov", "avi", "mkv"], key="vidup")
    if not up:
        st.info("Upload a 20 to 60 second clip with clearly visible cows (a side or high angle works best).")
        return
    tmp = Path(tempfile.mkdtemp(prefix="gd_in_")) / up.name
    tmp.write_bytes(up.getvalue())
    info = U.video_info(tmp)
    left, right = st.columns([3, 2], gap="large")
    with right:
        st.markdown("**Settings**")
        n_cows = st.number_input("How many cows can you see?", 1, 50, 2, key="n_cows")
        feed_on = st.checkbox("Mark the feed area", value=True, key="feed_on")
        fy = st.slider("Feed area, top to bottom (% of height)", 0, 100, (75, 100), disabled=not feed_on, key="feed_y")
        secs = st.slider("Analyse the first N seconds", 5, 180, int(min(max(info["duration"], 5), 60)), key="secs")
        conf = st.slider("Detection sensitivity (lower finds more cows)", 0.05, 0.7, 0.10, 0.05, key="conf")
        model = st.selectbox("Model", ["yolov8n.pt", "yolov8s.pt"], help="n = fast, s = more accurate", key="model")
        start = st.time_input("Video start time (clock)", dt.time(6, 0), key="vstart")
        st.caption("Behaviour thresholds are part of the verified backend and stay fixed. Tune them in colab/analysis.py if needed.")
    with left:
        frame = U.first_frame_bgr(tmp)
        if frame is not None:
            import cv2
            if feed_on:
                ov = frame.copy()
                cv2.rectangle(ov, (0, int(info["H"] * fy[0] / 100)), (info["W"], int(info["H"] * fy[1] / 100)), (0, 200, 0), -1)
                frame = cv2.addWeighted(ov, 0.28, frame, 0.72, 0)
            st.image(frame[:, :, ::-1], caption=f"{info['W']}x{info['H']} · {info['duration']:.0f} s · green = feed area", width="stretch")
    if st.button("▶ Analyze video", type="primary", key="run"):
        out = Path(tempfile.mkdtemp(prefix="gd_out_"))
        t0 = time.time()
        try:
            with st.status("Running YOLO + ByteTrack + behaviour analysis. This can take a few minutes on CPU...", expanded=True) as status_box:
                src_video = tmp
                if info["duration"] > secs + 0.5:
                    st.write(f"Trimming to the first {secs} s...")
                    src_video = U.trim_video(tmp, tmp.with_name("trim_" + tmp.stem + ".mp4"), secs)
                st.write("Detecting and tracking cows...")
                raw = U.run_pipeline(src_video, out, model, conf, (0, fy[0] / 100, 1, fy[1] / 100) if feed_on else None, start.strftime("%H:%M"))
                status_box.update(label=f"Done in {time.time() - t0:.0f} s", state="complete")
            if not raw["cows"]:
                st.error("No cows were tracked. Lower the sensitivity, or use a clearer clip.")
                return
            if len(raw["cows"]) > n_cows + 2:
                st.warning(f"Found {len(raw['cows'])} IDs for about {n_cows} cows. The tracker may be splitting cows; a steadier clip helps.")
            st.session_state["analysis"] = (U.normalize(raw), out)
            st.session_state["_goto_mine"] = True
            st.rerun()
        except Exception as e:
            st.error(f"Processing failed ({type(e).__name__}: {e}). Try a shorter clip. You can still use the demo herd or load Colab results.")


# ====================================================================== PAGE 7: ABOUT & METHOD
def about():
    st.markdown('<div class="sec">About & method</div>', unsafe_allow_html=True)
    st.markdown('<div class="flow">' + '<span class="a">→</span>'.join(f'<span class="n">{t}</span>' for t in (
        "CCTV video", "YOLO detection", "ByteTrack IDs", "Behaviour", "Own baseline", "Deviation", "Watchlist / alert", "Evidence clip", "Dashboard")) + "</div>", unsafe_allow_html=True)
    th = U.thresholds()
    st.markdown(f"""
**How a cow gets flagged**
- Each cow is compared **only with her own baseline** (the first part of the video), never with a fixed number for the whole herd.
- **Watchlist:** health deviation from {int(th['watch_from'] * 100)}% up to {int(th['health_alert'] * 100)}%, with at least one clear reason.
- **Alert:** health deviation of {int(th['health_alert'] * 100)}% or more, or a heat score of {int(th['heat_alert'] * 100)}% or more.
- **Herd Pulse** starts at 100 per cow. An alert costs up to 60 points and a watchlist case up to 35, weighted by its score.

**Honest limits**
- Behaviours are rule-based from box geometry, so every message says "possible". This is a screening aid, not a diagnosis. A vet confirms.
- The tracker can split one cow into two IDs in crowded scenes. A clear clip fixes most of this.
- Check Hindi and Telugu text with a native speaker before a real deployment.
""")
    chk = U.live_check()
    st.markdown('<div class="sec">System check: verified demo</div>', unsafe_allow_html=True)
    if chk is None:
        st.info("No data/live/results.json found, so the verified-demo check is skipped.")
    else:
        ok, rows = chk
        (st.success if ok else st.warning)("✅ The verified live results are intact." if ok else "⚠ data/live differs from the verified 2-cow result.")
        st.markdown("".join(f"- {'✅' if p else '❌'} {t}\n" for t, p in rows))
    st.caption("Frozen and unchanged: colab/analysis.py, colab/process_video.py, colab/verify_output.py, SCHEMA.md, data/live/. "
               "Run `python tests/check_frozen.py` to prove it.")


# ====================================================================== ROUTER
PAGES = {
    NAV[0]: overview,
    NAV[1]: analyze,
    NAV[2]: alerts_page,
    NAV[3]: watchlist_page,
    NAV[4]: health_cards,
    NAV[5]: herd_map,
    NAV[6]: evidence,
    NAV[7]: about,
}
safe(PAGES[page])
