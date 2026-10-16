"""Output: results.xlsx (Results / Review / Summary / Aspects) and results.jsonl. Never touches the input file."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .aspects import nlp_status

SKIP_REVIEW = {"CONSISTENT", "NO_COMPLAINT", "NO_DATA"}
HELPER_COLS = {"_stances", "like_none", "dislike_none"}


def build_sheets(out: pd.DataFrame, cfg: dict) -> dict[str, pd.DataFrame]:
    order = {lab: i for i, lab in enumerate(cfg["weights"]["severity_order"])}
    results = out.drop(columns=[c for c in HELPER_COLS if c in out.columns])
    review = results[~results["label"].isin(SKIP_REVIEW)].copy()
    review["_o"] = review["label"].map(order)
    review = review.sort_values(["_o", "confidence"], ascending=[True, False]).drop(columns="_o")
    review["human_label"] = ""
    counts = out["label"].value_counts().rename_axis("label").reset_index(name="rows")
    bucket = out.groupby(["label", "bucket"]).size().unstack(fill_value=0).reset_index()
    none_share = round(100 * (out["dislike_none"].isin(["NONE", "HEDGED_NONE"])).mean(), 1) if "dislike_none" in out else None
    notes = pd.DataFrame({"item": ["% Dislike answers none-ish", "spaCy / parser status", "corpus-generic nouns ignored"],
                          "value": [none_share, nlp_status() or "OK", ", ".join(out.attrs.get("generic_nouns", [])) or "-"]})
    asp = out[out["aspect"].astype(str) != ""]["aspect"].value_counts().rename_axis("aspect").reset_index(name="times_matched")
    return {"Results": results, "Review": review, "Summary": counts, "Summary_by_bucket": bucket, "Summary_notes": notes, "Aspects": asp}


def write_report(out: pd.DataFrame, cfg: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheets = build_sheets(out, cfg)
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, frame in sheets.items():
            frame.to_excel(xw, sheet_name=name[:31], index=False)
    with open(path.with_suffix(".jsonl"), "w", encoding="utf-8") as fh:
        for idx, row in out.iterrows():
            fh.write(json.dumps({"row": int(idx) if isinstance(idx, int) else str(idx), "label": row["label"],
                                 "confidence": row["confidence"], "stances": row.get("_stances", [])}, default=str) + "\n")
    return path
