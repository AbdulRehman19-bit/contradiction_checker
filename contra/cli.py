"""CLI:  python -m contra --input FILE.xlsx --sheet Sheet1 --out results.xlsx   |   --explain ROW"""
from __future__ import annotations

import argparse
import pandas as pd
import sys

from .config import load_config
from .engine import analyze_dataframe, explain_pair, fit_generic_nouns
from .io import ColumnDetectionError, detect_columns, read_table
from .report import write_report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="contra", description="Rule-based Like vs Dislike contradiction detector (no LLM).")
    ap.add_argument("--input", required=True)
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--like-col")
    ap.add_argument("--dislike-col")
    ap.add_argument("--out", default="output/results.xlsx")
    ap.add_argument("--config-dir", help="folder of YAML files that override the defaults")
    ap.add_argument("--gold-template", metavar="XLSX", help="write a stratified blind labelling template and exit")
    ap.add_argument("--evaluate", metavar="XLSX", help="evaluate a labelled gold template (dev / test report) and exit")
    ap.add_argument("--explain", type=int, metavar="ROW", help="print the full trace for one row index and exit")
    a = ap.parse_args(argv)

    df = read_table(a.input, a.sheet)
    try:
        like, dis = (a.like_col, a.dislike_col) if a.like_col and a.dislike_col else detect_columns(df)
    except ColumnDetectionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    cfg = load_config(a.config_dir)
    if a.explain is not None:
        extra = fit_generic_nouns(list(df[like]) + list(df[dis]), cfg)
        print(explain_pair(df.at[a.explain, like], df.at[a.explain, dis], {"cfg": cfg, "extra_generic": extra}))
        return 0
    if a.evaluate:
        from .gold import evaluate
        # re-run the CURRENT rules on the input, then compare with the human labels in the gold file
        fresh = analyze_dataframe(df, like, dis, cfg)
        preds = pd.DataFrame({"row_id": fresh.index, "pred_label": fresh["label"].values, "confidence": fresh["confidence"].values,
                              "bucket": fresh["bucket"].values, "rule_ids": fresh["rule_ids"].values})
        for split, rep in evaluate(a.evaluate, preds).items():
            print(f"=== {split} (n={rep['n']}) ===")
            print(rep["per_label"].round(2).to_string(index=False))
            print(rep["confusion"].to_string())
        return 0
    out = analyze_dataframe(df, like, dis, cfg)
    if a.gold_template:
        from .gold import write_gold_template
        print("gold template ->", write_gold_template(out, like, dis, a.gold_template))
        return 0
    path = write_report(out, cfg, a.out)
    print(f"{len(out)} rows -> {path}")
    print(out["label"].value_counts().to_string())
    for note in out.attrs.get("degraded", []):
        print("DEGRADED:", note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
