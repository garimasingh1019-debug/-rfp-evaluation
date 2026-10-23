"""Streamlit UI for the Agentic RFP Evaluation & Supplier Ranking project.

Run locally:  streamlit run app.py
"""
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

import db
import orchestrator
from tools import llm_agent

ROOT = Path(__file__).parent
SAMPLE_DIR = ROOT / "sample_pdfs"
SAMPLE_META = {  # suggested metadata for the four fictional sample proposals
    "Apex_Systems_RFP_Response.pdf": ("Apex Systems", date(2026, 3, 2), 8.0),
    "BrightPath_Tech_RFP_Response.pdf": ("BrightPath Tech", date(2026, 3, 5), 4.0),
    "NexaWorks_RFP_Response.pdf": ("NexaWorks", date(2026, 3, 4), 7.0),
    "Orbit_Digital_RFP_Response.pdf": ("Orbit Digital", date(2026, 3, 1), 9.0),
}

st.set_page_config(page_title="Agentic RFP Evaluation", page_icon="📑", layout="wide")
db.init_db()  # creates + seeds rfp.db on first start (also on Streamlit Cloud)


def secret_key():
    try:
        return st.secrets.get("OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    except Exception:  # no secrets file configured
        return os.environ.get("OPENAI_API_KEY", "")


# ----------------------------------------------------------------- sidebar
st.sidebar.title("📑 RFP Evaluation")
saved_key = secret_key()
demo_mode = st.sidebar.checkbox(
    "Demo mode (no OpenAI call)", value=not saved_key,
    help="Uses a simple keyword scorer so you can try the app without an API key. "
         "Scores are NOT real AI judgements.")
model = st.sidebar.text_input("OpenAI model", value="gpt-4o-mini", disabled=demo_mode)
typed_key = ""
if not demo_mode:
    if saved_key:
        st.sidebar.success("Using API key from app secrets.")
    else:
        typed_key = st.sidebar.text_input("OpenAI API key", type="password",
                                          help="Kept only in this browser session; never saved.")

st.sidebar.divider()
runs = db.list_runs()
st.sidebar.subheader("Previous runs")
if runs:
    pick = st.sidebar.selectbox("Open a saved run", [r["rfp_run_id"] for r in runs])
    if st.sidebar.button("Load run"):
        loaded = db.load_run(pick)
        if loaded and "suppliers" in loaded:
            st.session_state["result"] = loaded
        else:
            st.sidebar.error("That run has no stored results (it may have failed).")
else:
    st.sidebar.caption("No runs saved yet.")

st.title("Agentic RFP Evaluation and Supplier Ranking")
st.caption("The AI reads and scores each proposal. Python does all maths, benchmarks, tie-breaks and ranks.")

tab_criteria, tab_input, tab_board, tab_cards, tab_run = st.tabs(
    ["1 · Criteria", "2 · Supplier input", "3 · Leaderboard", "4 · Scorecards", "5 · Run details"])

# ----------------------------------------------------------------- 1. criteria
with tab_criteria:
    st.subheader("Evaluation criteria")
    st.write("Stored in SQLite. Change a weight or tick/untick *Active*, then press Save. "
             "The next evaluation always uses the latest active criteria.")
    crit_df = pd.DataFrame(db.get_criteria(active_only=False))
    crit_df["is_active"] = crit_df["is_active"].astype(bool)
    edited = st.data_editor(
        crit_df, hide_index=True, use_container_width=True, key="crit_editor",
        disabled=["criterion_id", "name", "description"],
        column_config={
            "criterion_id": "ID", "name": "Criterion", "description": "What the AI inspects",
            "weight": st.column_config.NumberColumn("Weight %", min_value=0.0, max_value=100.0, step=1.0),
            "max_score": st.column_config.NumberColumn("Max score", min_value=1.0, step=1.0),
            "is_active": st.column_config.CheckboxColumn("Active"),
        })
    total = float(edited.loc[edited["is_active"], "weight"].sum())
    c1, c2 = st.columns([1, 3])
    c1.metric("Active weight total", f"{total:g}%")
    if abs(total - 100) > 1e-6:
        c2.warning("Active weights should total 100%. If they don't, the app rescales them "
                   "proportionally and records a warning.")
    else:
        c2.success("Weights total 100%.")
    if st.button("Save criteria"):
        db.update_criteria(edited.to_dict("records"))
        st.success("Saved.")
        st.rerun()

# ----------------------------------------------------------------- 2. input
with tab_input:
    st.subheader("Upload supplier proposals")
    uploads = st.file_uploader("Supplier RFP responses (PDF)", type="pdf", accept_multiple_files=True)
    use_samples = st.checkbox("Use the 4 fictional sample proposals instead", value=False)

    docs = []  # (filename, bytes, default name, default date, default rating)
    if use_samples:
        for fname, (nm, dt, rt) in SAMPLE_META.items():
            path = SAMPLE_DIR / fname
            if path.exists():
                docs.append((fname, path.read_bytes(), nm, dt, rt))
    else:
        for f in uploads or []:
            docs.append((f.name, f.getvalue(), Path(f.name).stem.replace("_", " ").replace("RFP Response", "").strip(),
                         date.today(), 5.0))

    rows = []
    if docs:
        st.write("Enter details for each proposal:")
        for i, (fname, data, dname, ddate, drate) in enumerate(docs):
            key = f"{'s' if use_samples else 'u'}_{i}_{fname}"
            c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
            c1.markdown(f"**{fname}**  \n{len(data) / 1024:.0f} KB")
            name = c2.text_input("Supplier name", value=dname, key=f"name_{key}")
            sdate = c3.date_input("Submission date", value=ddate, key=f"date_{key}")
            rating = c4.number_input("Experience rating (0-10)", min_value=0.0, max_value=10.0,
                                     value=float(drate), step=0.5, key=f"rate_{key}")
            rows.append({"name": name, "submission_date": sdate, "experience_rating": rating,
                         "filename": fname, "pdf_bytes": data})
    else:
        st.info("Upload two or more PDFs, or tick the sample option, to begin.")

    errors, warns = orchestrator.validate_inputs(rows) if rows else ([], [])
    for m in errors:
        st.error(m)
    for m in warns:
        st.warning(m)

    needs_key = (not demo_mode) and not (saved_key or typed_key)
    if needs_key:
        st.warning("Enter your OpenAI API key in the sidebar, or switch on demo mode.")
    if demo_mode:
        st.info("Demo mode is ON: scores come from a keyword scorer, not an AI model.")

    if st.button("Evaluate", type="primary", disabled=bool(errors) or not rows or needs_key):
        try:
            llm = llm_agent.MockLLM() if demo_mode else llm_agent.OpenAILLM(saved_key or typed_key, model)
            with st.status("Evaluating ...", expanded=True) as status:
                result = orchestrator.run_evaluation(rows, llm, progress=lambda m: st.write(m))
                status.update(label=f"Done · {result['rfp_run_id']}", state="complete")
            st.session_state["result"] = result
            st.success(f"Run {result['rfp_run_id']} saved. Open the Leaderboard tab.")
        except Exception as exc:  # noqa: BLE001 - show any failure to the user
            st.error(f"Evaluation failed: {exc}")

# ----------------------------------------------------------------- results
result = st.session_state.get("result")


def need_result():
    st.info("No results yet. Run an evaluation (tab 2) or load a saved run from the sidebar.")


with tab_board:
    if not result:
        need_result()
    else:
        if result["llm"]["mode"] == "demo":
            st.warning("These results come from DEMO mode (keyword scorer), not an AI model.")
        top = result["suppliers"][0]
        st.success(f"🏆 Rank 1: **{top['supplier_name']}**  ·  PPI {top['ppi']:.2f}  ·  "
                   f"Absolute score {top['absolute_score']:.2f}")
        board = pd.DataFrame([{
            "Rank": s["rank"], "Supplier": s["supplier_name"], "Absolute score": s["absolute_score"],
            "PPI": s["ppi"], "Submission date": s["submission_date"],
            "Experience rating": s["experience_rating"], "Why this rank": s["rank_reason"]}
            for s in result["suppliers"]])
        st.dataframe(board, hide_index=True, use_container_width=True)
        st.bar_chart(board.set_index("Supplier")[["Absolute score", "PPI"]])

with tab_cards:
    if not result:
        need_result()
    else:
        names = [s["supplier_name"] for s in result["suppliers"]]
        chosen = st.selectbox("Supplier", names)
        s = next(x for x in result["suppliers"] if x["supplier_name"] == chosen)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Rank", s["rank"])
        m2.metric("Absolute score", f"{s['absolute_score']:.2f}")
        m3.metric("PPI", f"{s['ppi']:.2f}")
        m4.metric("Evaluation", s["evaluation_status"])
        st.caption(s["rank_reason"])
        detail = pd.DataFrame([{
            "Criterion": d["criterion"], "Weight %": d["weight"], "Score": d["score"],
            "Max": d["max_score"], "Benchmark": d["benchmark"], "Gap": d["gap"],
            "Relative %": d["relative_pct"], "Flag": d["flag"]} for d in s["criteria_detail"]])
        st.dataframe(detail, hide_index=True, use_container_width=True)
        st.markdown("#### Justification and evidence")
        for d in s["criteria_detail"]:
            with st.expander(f"{d['criterion']} — {d['score']:g}/{d['max_score']:g}"):
                st.markdown(f"**Justification:** {d['justification'] or '—'}")
                st.markdown(f"**Evidence:** {d['evidence'] or '—'}")
        if s["overall_summary"]:
            st.markdown(f"**Summary:** {s['overall_summary']}")
        if s["risks"]:
            st.markdown("**Risks:**\n" + "\n".join(f"- {r}" for r in s["risks"]))
        st.markdown("#### All suppliers: relative performance % per criterion")
        grid = {x["supplier_name"]: {d["criterion"]: d["relative_pct"] for d in x["criteria_detail"]}
                for x in result["suppliers"]}
        st.dataframe(pd.DataFrame(grid), use_container_width=True)

with tab_run:
    if not result:
        need_result()
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("RFP_RUN_ID", result["rfp_run_id"])
        c2.metric("Status", result["status"])
        c3.metric("Scorer", f"{result['llm']['mode']} {result['llm'].get('model', '')}".strip())
        st.markdown("#### Tie-break explanation")
        for t in result["tie_break_explanation"]:
            st.write("• " + t)
        st.markdown("#### Warnings")
        if result["warnings"]:
            for w in result["warnings"]:
                st.warning(w)
        else:
            st.success("No warnings.")
        st.markdown("#### Criteria used in this run")
        st.dataframe(pd.DataFrame(result["criteria"]), hide_index=True, use_container_width=True)
        st.markdown("#### Formulas")
        st.json(result["formulas"])
        st.download_button("⬇ Download complete result (JSON)", data=json.dumps(result, indent=2),
                           file_name=f"{result['rfp_run_id']}.json", mime="application/json")
