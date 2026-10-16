"""Streamlit frontend for the Like-vs-Dislike contradiction detector (thin layer over the contra engine)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from contra.aspects import nlp_status  # noqa: E402
from contra.config import load_config  # noqa: E402
from contra.engine import analyze_dataframe, explain_pair, fit_generic_nouns  # noqa: E402
from contra.io import ColumnDetectionError, detect_columns  # noqa: E402
from contra.report import build_sheets, write_workbook  # noqa: E402

DATA_DIR = ROOT / "data"
st.set_page_config(page_title="Like vs Dislike checker", layout="wide")
st.title("Like vs Dislike checker")
st.caption("Finds answers where the Like and Dislike text disagree or are in the wrong box. Rule-based, no AI model; every row shows why.")

base_cfg = load_config()
COLORS = base_cfg["colors"]["labels"]

# ------------------------------------------------------------------ sidebar: data
with st.sidebar:
    st.header("1. Choose your data")
    uploaded = st.file_uploader("Upload an Excel or CSV file", type=["xlsx", "xls", "csv", "tsv"])
    local = sorted(p.name for p in DATA_DIR.glob("*") if p.suffix.lower() in {".xlsx", ".xls", ".csv", ".tsv"})
    picked = st.selectbox("...or pick a file from the data folder", ["-"] + local)

source, name = None, None
if uploaded is not None:
    source, name = io.BytesIO(uploaded.getvalue()), uploaded.name
elif picked != "-":
    source, name = DATA_DIR / picked, picked
if source is None:
    st.info("Upload a file or put one in the `data` folder, then pick it in the sidebar. The analysis starts automatically.")
    st.stop()

suffix = Path(name).suffix.lower()
sheet = None
if suffix in {".xlsx", ".xls"}:
    sheets = pd.ExcelFile(source).sheet_names
    if hasattr(source, "seek"):
        source.seek(0)
    with st.sidebar:
        sheet = st.selectbox("Sheet", sheets, index=sheets.index("Sheet1") if "Sheet1" in sheets else 0)
    df = pd.read_excel(source, sheet_name=sheet)
else:
    df = pd.read_csv(source, sep="\t" if suffix == ".tsv" else ",")

cols = [str(c) for c in df.columns]
try:
    g_like, g_dis = detect_columns(df)
except ColumnDetectionError:
    g_like, g_dis = cols[0], cols[min(1, len(cols) - 1)]
with st.sidebar:
    like_col = st.selectbox("Column with the LIKE answers", cols, index=cols.index(g_like))
    dis_col = st.selectbox("Column with the DISLIKE answers", cols, index=cols.index(g_dis))

# ------------------------------------------------------------------ sidebar: advanced (hidden by default)
overrides: dict[str, dict] = {}
with st.sidebar:
    with st.expander("Advanced options"):
        product_terms = st.text_input("Words to ignore as topics (comma separated)", "",
                                      help="Words that just mean 'the product', e.g. the product's own name.")
        st.caption("All matching rules are plain word lists. Edit one and the results refresh. "
                   "Edits last for this session; save them in contra/config to keep them.")
        stem = st.selectbox("Word list file", sorted(base_cfg))
        text = st.text_area(f"{stem}.yaml", yaml.safe_dump(base_cfg[stem], sort_keys=False, allow_unicode=True), height=260)
        try:
            edited = yaml.safe_load(text) or {}
            if edited != base_cfg[stem]:
                overrides[stem] = edited
                st.success(f"{stem}.yaml changed for this session")
        except yaml.YAMLError as exc:
            st.error(f"Not valid YAML, ignored: {exc}")

cfg = load_config(overrides=overrides)
if product_terms.strip():
    cfg["aspects"]["product_terms"] = [t.strip() for t in product_terms.split(",") if t.strip()]

# ------------------------------------------------------------------ analysis runs automatically when anything changes
signature = (name, sheet, like_col, dis_col, product_terms, yaml.safe_dump(overrides, sort_keys=True))
if st.session_state.get("sig") != signature:
    with st.spinner("Analysing..."):
        st.session_state["out"] = analyze_dataframe(df, like_col, dis_col, cfg)
        st.session_state["extra"] = fit_generic_nouns(list(df[like_col]) + list(df[dis_col]), cfg)
        st.session_state["sig"] = signature
out: pd.DataFrame = st.session_state["out"]

if nlp_status():
    st.warning(nlp_status())

# ------------------------------------------------------------------ colour legend with counts
order = cfg["weights"]["severity_order"]
counts = out["label"].value_counts()
chips = " ".join(
    f'<span title="{COLORS[l]["meaning"]}" style="background:#{COLORS[l]["fill"]};color:#222;border-left:6px solid #{COLORS[l]["strong"]};'
    f'padding:4px 10px;margin:2px;border-radius:4px;display:inline-block;font-size:0.85rem">'
    f'<b>{l.replace("_", " ").title()}</b>: {counts.get(l, 0)} &nbsp;<span style="opacity:.7">{COLORS[l]["meaning"]}</span></span>'
    for l in order if counts.get(l, 0))
st.markdown(f"**{len(out)} rows analysed.** Colours:<br>{chips}", unsafe_allow_html=True)

# ------------------------------------------------------------------ simple filters
st.markdown("#### Filter")
f1, f2, f3 = st.columns([2, 2, 3])
mode = f1.radio("Show", ["All rows", "Only rows to review", "Pick findings"],
                help="'Only rows to review' hides rows with no conflict, a clean 'nothing', or no data.")
conf = f2.radio("How sure is the system?", ["Any", "Medium or higher", "High only"],
                help="Confidence of the finding. Low = a weak hint, High = strong evidence.")
query = f3.text_input("Search the answers", placeholder="type a word, e.g. sweet")

view = out
if mode == "Only rows to review":
    view = view[~view["label"].isin(cfg["colors"]["not_a_problem"])]
elif mode == "Pick findings":
    chosen = f3.multiselect("Findings to show", [l for l in order if counts.get(l, 0)],
                            default=[l for l in order if counts.get(l, 0) and l not in cfg["colors"]["not_a_problem"]],
                            format_func=lambda l: f"{l.replace('_', ' ').title()} - {COLORS[l]['meaning']}")
    view = view[view["label"].isin(chosen)]
if conf == "Medium or higher":
    view = view[view["bucket"].isin(["HIGH", "MED"])]
elif conf == "High only":
    view = view[view["bucket"] == "HIGH"]
if query:
    q = query.lower()
    view = view[view[like_col].astype(str).str.lower().str.contains(q, regex=False)
                | view[dis_col].astype(str).str.lower().str.contains(q, regex=False)]

# file order when showing everything, most serious first otherwise
if mode != "All rows":
    sev = {l: i for i, l in enumerate(order)}
    view = view.assign(_o=view["label"].map(sev)).sort_values(["_o", "confidence"], ascending=[True, False]).drop(columns="_o")

# ------------------------------------------------------------------ colour-coded table
st.markdown(f"#### {len(view)} of {len(out)} rows")
table = view[[like_col, dis_col, "label", "confidence", "explanation"]].rename(columns={
    like_col: "LIKE", dis_col: "DISLIKE", "label": "Finding", "confidence": "Confidence", "explanation": "Why"})
table.index.name = "Row"


def _paint(row):
    spec = COLORS.get(row["Finding"])
    return [f"background-color:#{spec['fill']};color:#222" if spec else ""] * len(row)


event = st.dataframe(table.style.apply(_paint, axis=1), width="stretch", height=430,
                     on_select="rerun", selection_mode="single-row",
                     column_config={"Confidence": st.column_config.NumberColumn(format="%.2f", width="small"),
                                    "LIKE": st.column_config.TextColumn(width="large"),
                                    "DISLIKE": st.column_config.TextColumn(width="large"),
                                    "Why": st.column_config.TextColumn(width="large")})

# ------------------------------------------------------------------ detail for the clicked row
sel = event.selection.rows if event and event.selection else []
if sel:
    idx = view.index[sel[0]]
    row = out.loc[idx]
    spec = COLORS.get(row["label"], {})
    st.markdown(f'<div style="background:#{spec.get("fill","eee")};color:#222;padding:8px 12px;border-left:6px solid #{spec.get("strong","999")}">'
                f'<b>Row {idx}: {row["label"].replace("_", " ").title()}</b> ({row["bucket"].title()} confidence, {row["confidence"]})<br>'
                f'{row["explanation"]}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.markdown(f"**LIKE**\n\n{row[like_col]}")
    c2.markdown(f"**DISLIKE**\n\n{row[dis_col]}")
    with st.expander("How the system decided (technical trace)"):
        st.code(explain_pair(row[like_col], row[dis_col], {"cfg": cfg, "extra_generic": st.session_state["extra"]}))
else:
    st.caption("Click a row to see the two answers side by side and how it was decided.")

# ------------------------------------------------------------------ download (colour-coded workbook)
buf = io.BytesIO()
write_workbook(build_sheets(out, cfg), cfg, buf)
st.download_button("Download colour-coded Excel", buf.getvalue(), file_name="results.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
