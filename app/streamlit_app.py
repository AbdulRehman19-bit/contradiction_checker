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
from contra.io import ColumnDetectionError, detect_columns, list_sheets, read_table  # noqa: E402
from contra.report import build_sheets  # noqa: E402

DATA_DIR = ROOT / "data"
st.set_page_config(page_title="Like vs Dislike checker", layout="wide")
st.title("Like vs Dislike contradiction checker")
st.caption("Rule-based, no LLM. Every flag shows its evidence and the rule that fired.")

# ------------------------------------------------------------------ sidebar: data
with st.sidebar:
    st.header("1. Data")
    uploaded = st.file_uploader("Upload xlsx / csv", type=["xlsx", "xls", "csv", "tsv"])
    local = sorted(p.name for p in DATA_DIR.glob("*") if p.suffix.lower() in {".xlsx", ".xls", ".csv", ".tsv"})
    picked = st.selectbox("...or use a file from data/", ["-"] + local)

source, name = None, None
if uploaded is not None:
    source, name = io.BytesIO(uploaded.getvalue()), uploaded.name
elif picked != "-":
    source, name = DATA_DIR / picked, picked

if source is None:
    st.info("Upload a file or put one in the `data/` folder, then choose it in the sidebar.")
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
    guess_like, guess_dis = detect_columns(df)
except ColumnDetectionError:
    guess_like, guess_dis = cols[0], cols[min(1, len(cols) - 1)]
with st.sidebar:
    like_col = st.selectbox("LIKE column", cols, index=cols.index(guess_like))
    dis_col = st.selectbox("DISLIKE column", cols, index=cols.index(guess_dis))

# ------------------------------------------------------------------ sidebar: editable lexicons
base_cfg = load_config()
overrides: dict[str, dict] = {}
with st.sidebar:
    st.header("2. Rules (editable, no code)")
    st.caption("Change a word list and press Run. Edits apply to this session only; save to the YAML files in contra/config to keep them.")
    product_terms = st.text_input("Product words to ignore as aspects (comma separated, optional)", "")
    stem = st.selectbox("Lexicon file", sorted(base_cfg))
    text = st.text_area(f"{stem}.yaml", yaml.safe_dump(base_cfg[stem], sort_keys=False, allow_unicode=True), height=300)
    try:
        edited = yaml.safe_load(text) or {}
        if edited != base_cfg[stem]:
            overrides[stem] = edited
            st.success(f"{stem}.yaml modified for this run")
    except yaml.YAMLError as exc:
        st.error(f"Invalid YAML, ignored: {exc}")
    run = st.button("Run analysis", type="primary", width="stretch")

cfg = load_config(overrides=overrides)
if product_terms.strip():
    cfg["aspects"]["product_terms"] = [t.strip() for t in product_terms.split(",") if t.strip()]

if run:
    with st.spinner("Analysing..."):
        out = analyze_dataframe(df, like_col, dis_col, cfg)
        st.session_state["out"] = out
        st.session_state["cfg"] = cfg
        st.session_state["cols"] = (like_col, dis_col)
        st.session_state["extra"] = fit_generic_nouns(list(df[like_col]) + list(df[dis_col]), cfg)

if "out" not in st.session_state:
    st.subheader("Preview")
    st.dataframe(df.head(20), width="stretch")
    st.info("Press **Run analysis** in the sidebar.")
    st.stop()

out: pd.DataFrame = st.session_state["out"]
cfg = st.session_state["cfg"]
like_col, dis_col = st.session_state["cols"]

# ------------------------------------------------------------------ summary
degraded = nlp_status()
if degraded:
    st.warning(degraded)
order = cfg["weights"]["severity_order"]
counts = out["label"].value_counts().reindex(order).dropna().astype(int)
mc = st.columns(len(counts))
for col, (lab, n) in zip(mc, counts.items()):
    col.metric(lab, n)
gen = out.attrs.get("generic_nouns", [])
if gen:
    st.caption("Ignored as non-aspect (learned from this data): " + ", ".join(gen))

# ------------------------------------------------------------------ filters
f1, f2, f3, f4 = st.columns([3, 2, 2, 3])
labels = f1.multiselect("Label", order, default=[l for l in order if l not in {"CONSISTENT", "NO_COMPLAINT", "NO_DATA"}])
buckets = f2.multiselect("Confidence", ["HIGH", "MED", "LOW"], default=["HIGH", "MED", "LOW"])
min_conf = f3.slider("Min confidence", 0.0, 1.0, 0.0, 0.05)
query = f4.text_input("Search text")
view = out[out["label"].isin(labels) & out["bucket"].isin(buckets) & (out["confidence"] >= min_conf)]
if query:
    q = query.lower()
    view = view[view[like_col].astype(str).str.lower().str.contains(q) | view[dis_col].astype(str).str.lower().str.contains(q)]
sev = {l: i for i, l in enumerate(order)}
view = view.assign(_o=view["label"].map(sev)).sort_values(["_o", "confidence"], ascending=[True, False]).drop(columns="_o")

show = [like_col, dis_col, "label", "confidence", "bucket", "aspect", "extra_flags", "explanation"]
st.subheader(f"{len(view)} rows")
event = st.dataframe(view[show], width="stretch", height=380, on_select="rerun", selection_mode="single-row")

# ------------------------------------------------------------------ detail / trace
sel = event.selection.rows if event and event.selection else []
if sel:
    idx = view.index[sel[0]]
    row = out.loc[idx]
    st.subheader(f"Row {idx}: {row['label']} ({row['bucket']}, {row['confidence']})")
    c1, c2 = st.columns(2)
    c1.markdown(f"**LIKE**\n\n{row[like_col]}")
    c2.markdown(f"**DISLIKE**\n\n{row[dis_col]}")
    st.write(row["explanation"])
    st.caption(f"Rules: {row['rule_ids']}")
    with st.expander("Full parse trace (clauses, aspects, stances, candidates)", expanded=True):
        st.code(explain_pair(row[like_col], row[dis_col], {"cfg": cfg, "extra_generic": st.session_state["extra"]}))
else:
    st.caption("Click a row in the table to see its clause / aspect / rule trace.")

# ------------------------------------------------------------------ download
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    for sheet_name, frame in build_sheets(out, cfg).items():
        frame.to_excel(xw, sheet_name=sheet_name[:31], index=False)
st.download_button("Download results.xlsx", buf.getvalue(), file_name="results.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
