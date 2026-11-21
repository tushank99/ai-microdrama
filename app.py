"""Cliffhanger Auditor - Streamlit frontend.

Local:  streamlit run app.py          (keys read from .env)
Cloud:  set GROQ_API_KEY / GEMINI_API_KEY in the app's Secrets.
"""
import html
import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# Streamlit Cloud secrets -> environment, before the auditor reads it.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:
    pass

from auditor import llm  # noqa: E402
from auditor.audit import audit  # noqa: E402
from auditor.parse import parse_screenplay  # noqa: E402

ROOT = Path(__file__).parent
SAMPLES = {p.stem.replace("show_", "").replace("_", " ").title(): p
           for p in sorted((ROOT / "inputs").glob("show_*.txt"))}
PROVIDER_LABELS = {"groq": "Groq", "gemini": "Google Gemini", "openai": "OpenAI-compatible",
                   "anthropic": "Anthropic", "none": "Rules only (no LLM)"}
FORMAT_HELP = """EPISODE 1: Title
[00:00] INT. BALLROOM - NIGHT. A glass shatters.
[00:02] VICTORIA: You dare wear my mother's necklace?
[01:15] ADRIAN: The last woman who wore it died in my house.

EPISODE 2: Title
..."""

st.set_page_config(page_title="Cliffhanger Auditor", page_icon="🎬", layout="wide")

st.markdown("""
<style>
  .block-container {padding-top: 2rem; max-width: 1200px;}
  .flag {display:inline-block; padding:2px 8px; margin:0 4px 4px 0; border-radius:4px;
         font-size:0.75rem; font-weight:600; background:#fde8e8; color:#9b1c1c;}
  .flag.PAYWALL_RISK {background:#fdf2d8; color:#8a5a00;}
  .flag.HUMAN_CHECK {background:#e1effe; color:#1e429f;}
  .beat {font-family: ui-monospace, monospace; font-size: 0.85rem; white-space: pre-wrap;
         background: rgba(127,127,127,0.08); padding: 0.6rem 0.8rem; border-radius: 6px;}
</style>
""", unsafe_allow_html=True)

st.title("Cliffhanger Auditor")
st.write("Script-stage quality check for vertical microdramas. Each episode is scored on its "
         "**opening hook** and **closing cliffhanger**; weak episodes are flagged with a suggested "
         "rewrite of the final beat.")

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Settings")
    configured = llm.available_providers()
    options = configured + ["none"]
    provider = st.selectbox("Scoring model", options, format_func=lambda p: PROVIDER_LABELS.get(p, p))
    model = ""
    if provider != "none":
        model = st.text_input("Model ID", value=llm.DEFAULT_MODELS.get(provider, ""))
    paywall = st.number_input("Paywall episode", min_value=1, max_value=500, value=10,
                              help="Episodes adjacent to this one are held to a stricter cliffhanger threshold.")
    threshold = st.slider("Flag scores below", 1, 10, 6)
    st.divider()
    st.caption("Scoring: an LLM judge reads the first ~15 s and last ~20 s of every episode. "
               "Keyword rules run alongside; large disagreements are marked HUMAN_CHECK.")

# ------------------------------------------------------------------ input
tab_sample, tab_upload, tab_paste = st.tabs(["Sample script", "Upload .txt", "Paste text"])
with tab_sample:
    sample = st.selectbox("Sample", list(SAMPLES))
with tab_upload:
    upload = st.file_uploader("Screenplay (.txt)", type=["txt"])
with tab_paste:
    pasted = st.text_area("Screenplay text", height=220, placeholder=FORMAT_HELP)
with st.expander("Expected script format"):
    st.code(FORMAT_HELP, language="text")

if upload is not None:
    text, source = upload.read().decode("utf-8", errors="replace"), upload.name
elif pasted.strip():
    text, source = pasted, "pasted text"
else:
    text, source = SAMPLES[sample].read_text(encoding="utf-8"), SAMPLES[sample].name

st.caption(f"Input: **{source}**")

if st.button("Run audit", type="primary"):
    episodes = parse_screenplay(text)
    if not episodes:
        st.error("No episodes found. Each episode must start with a line like `EPISODE 1: Title` "
                 "and beats must start with `[mm:ss]`.")
        st.stop()
    with st.spinner(f"Scoring {len(episodes)} episodes with {PROVIDER_LABELS.get(provider, provider)}..."):
        rows = audit(episodes, paywall_ep=int(paywall), threshold=threshold,
                     provider=provider, model=model or None)
    st.session_state["result"] = {
        "df": pd.DataFrame(rows), "source": source, "threshold": threshold,
        "endings": {e.number: e.ending() for e in episodes},
        "openings": {e.number: e.opening() for e in episodes},
    }

# ------------------------------------------------------------------ results
res = st.session_state.get("result")
if res:
    df, thr = res["df"], res["threshold"]
    if df["llm_error"].iloc[0]:
        st.warning(f"Model call failed; scores below are rules-only. Detail: {df['llm_error'].iloc[0]}")

    n_cliff = int(df["flags"].str.contains("WEAK_CLIFFHANGER").sum())
    n_hook = int(df["flags"].str.contains("WEAK_HOOK").sum())
    n_pay = int(df["flags"].str.contains("PAYWALL_RISK").sum())
    c = st.columns(4)
    c[0].metric("Episodes", len(df))
    c[1].metric("Weak cliffhangers", n_cliff)
    c[2].metric("Weak hooks", n_hook)
    c[3].metric("Paywall risk", n_pay)

    long = df.melt(id_vars=["episode", "title"], value_vars=["hook_score", "cliff_score"],
                   var_name="metric", value_name="score")
    long["metric"] = long["metric"].map({"hook_score": "Hook", "cliff_score": "Cliffhanger"})
    bars = alt.Chart(long).mark_bar().encode(
        x=alt.X("episode:O", title="Episode"),
        xOffset="metric:N",
        y=alt.Y("score:Q", scale=alt.Scale(domain=[0, 10]), title="Score"),
        color=alt.Color("metric:N", scale=alt.Scale(range=["#2563eb", "#f59e0b"]), title=None),
        tooltip=["episode", "title", "metric", "score"])
    rule = alt.Chart(pd.DataFrame({"y": [thr]})).mark_rule(strokeDash=[4, 4], color="#dc2626").encode(y="y:Q")
    st.altair_chart((bars + rule).properties(height=260), use_container_width=True)

    flagged = df[df["flags"] != ""]
    st.subheader(f"Flagged episodes ({len(flagged)})")
    if flagged.empty:
        st.success("No episodes below threshold.")
    for r in flagged.itertuples():
        chips = "".join(f'<span class="flag {f}">{f}</span>' for f in r.flags.split(","))
        with st.expander(f"Episode {r.episode}: {r.title}  |  hook {r.hook_score}  ·  cliffhanger {r.cliff_score}"):
            st.markdown(chips, unsafe_allow_html=True)
            left, right = st.columns(2)
            with left:
                st.markdown("**Opening**")
                st.markdown(f'<div class="beat">{html.escape(res["openings"][r.episode])}</div>', unsafe_allow_html=True)
            with right:
                st.markdown("**Ending**")
                st.markdown(f'<div class="beat">{html.escape(res["endings"][r.episode])}</div>', unsafe_allow_html=True)
            st.markdown(f"**Issue:** {r.issue}")
            st.markdown(f"**Suggested final beat:** {r.fix}")
            st.caption(f"Cliffhanger type: {r.cliff_type} · Rule scores: hook {r.rule_hook}, "
                       f"cliffhanger {r.rule_cliff} · Scored by: {r.scored_by}")

    st.subheader("All episodes")
    view = df[["episode", "title", "hook_score", "cliff_score", "cliff_type", "flags", "issue", "fix"]]
    st.dataframe(view, use_container_width=True, hide_index=True,
                 column_config={
                     "hook_score": st.column_config.ProgressColumn("Hook", min_value=0, max_value=10, format="%d"),
                     "cliff_score": st.column_config.ProgressColumn("Cliffhanger", min_value=0, max_value=10, format="%d"),
                 })
    stem = Path(res["source"]).stem.replace(" ", "_")
    d1, d2 = st.columns(2)
    d1.download_button("Download CSV", df.drop(columns=["llm_error"]).to_csv(index=False),
                       f"audit_{stem}.csv", "text/csv", use_container_width=True)
    d2.download_button("Download JSON", df.drop(columns=["llm_error"]).to_json(orient="records", indent=2),
                       f"audit_{stem}.json", "application/json", use_container_width=True)
