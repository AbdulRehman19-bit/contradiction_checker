"""Gold-set tooling: stratified labelling template, then dev/test evaluation once the user has labelled it."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl.worksheet.datavalidation import DataValidation

LABELS = ["CONTRADICTION", "TENSION", "MISPLACED_POSITIVE", "MISPLACED_NEGATIVE", "SELF_CONFLICT",
          "CONSISTENT", "NO_COMPLAINT", "NO_DATA"]
# rows per predicted label (flagged classes oversampled); "NEAR_MISS" = CONSISTENT rows sharing a content word
QUOTAS = {"CONTRADICTION": 99, "BARE_ASPECT_CONFLICT": 99, "SELF_CONFLICT": 99, "MISPLACED_POSITIVE": 99,
          "MISPLACED_NEGATIVE": 99, "TENSION": 28, "NEAR_MISS": 25, "CONSISTENT": 20, "NO_COMPLAINT": 8, "NO_DATA": 2}
_STOP = set("the a an and of to is it in this that i very with for on are as be its my me not no but too more was so have has "
            "like good taste".split())


def _words(s) -> set:
    return set(re.findall(r"[a-z]{3,}", str(s).lower())) - _STOP


def stratified_sample(out: pd.DataFrame, like_col: str, dis_col: str, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    overlap = np.array([bool(_words(a) & _words(b)) for a, b in zip(out[like_col], out[dis_col])])
    near = out.index[(out["label"] == "CONSISTENT").to_numpy() & overlap]
    picked: list = []
    for strat, quota in QUOTAS.items():
        pool = list(near) if strat == "NEAR_MISS" else [i for i in out.index[out["label"] == strat] if i not in picked]
        pool = [i for i in pool if i not in picked]
        take = min(quota, len(pool))
        picked += list(rng.choice(pool, size=take, replace=False)) if take else []
    return out.loc[sorted(picked)]


def write_gold_template(out: pd.DataFrame, like_col: str, dis_col: str, path: str | Path, seed: int = 7) -> Path:
    """Blind labelling sheet (no predictions shown) + a separate Predictions sheet keyed by row_id."""
    sample = stratified_sample(out, like_col, dis_col, seed)
    rng = np.random.default_rng(seed)
    split = rng.permutation(["dev", "test"] * (len(sample) // 2 + 1))[: len(sample)]
    sheet = pd.DataFrame({"row_id": sample.index, "split": split, "LIKE": sample[like_col].values,
                          "DISLIKE": sample[dis_col].values, "human_label": "", "notes": ""})
    preds = pd.DataFrame({"row_id": sample.index, "pred_label": sample["label"].values, "confidence": sample["confidence"].values,
                          "bucket": sample["bucket"].values, "rule_ids": sample["rule_ids"].values})
    guide = pd.DataFrame({"label": LABELS, "meaning": [
        "Same aspect, opposite stance (Like: 'I like the taste' / Dislike: 'I do not like the taste')",
        "Related aspects or degree differences; a human should look (e.g. Like 'sweet note is nice' / Dislike 'too sugary')",
        "Dislike answer is really praise ('I loved it', 'nothing against it, I like the taste')",
        "Like answer contains a complaint ('a little sweet but oh well')",
        "Dislike starts with 'nothing' then adds a complaint ('Nothing, just needs more filling')",
        "Both answers have content and do not conflict",
        "Dislike is a clean 'nothing / no complaints'",
        "One side blank or unusable"]})
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        sheet.to_excel(xw, sheet_name="Label", index=False)
        guide.to_excel(xw, sheet_name="Guide", index=False)
        preds.to_excel(xw, sheet_name="Predictions", index=False)
        ws = xw.sheets["Label"]
        dv = DataValidation(type="list", formula1='"' + ",".join(LABELS) + '"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"E2:E{len(sheet) + 1}")
        for col, width in zip("ABCDEF", (8, 7, 60, 60, 22, 30)):
            ws.column_dimensions[col].width = width
    return path


def evaluate(labelled_path: str | Path, predictions: pd.DataFrame | None = None) -> dict:
    """Per-label precision/recall/F1 + confusion matrix, reported separately for dev and test."""
    lab = pd.read_excel(labelled_path, sheet_name="Label")
    pred = pd.read_excel(labelled_path, sheet_name="Predictions") if predictions is None else predictions
    df = lab.merge(pred, on="row_id")
    df = df[df["human_label"].astype(str).str.strip() != ""]
    report = {}
    for split, part in [("dev", df[df["split"] == "dev"]), ("test", df[df["split"] == "test"]), ("all", df)]:
        rows = []
        for L in LABELS:
            tp = int(((part["pred_label"] == L) & (part["human_label"] == L)).sum())
            fp = int(((part["pred_label"] == L) & (part["human_label"] != L)).sum())
            fn = int(((part["pred_label"] != L) & (part["human_label"] == L)).sum())
            p = tp / (tp + fp) if tp + fp else float("nan")
            r = tp / (tp + fn) if tp + fn else float("nan")
            f = 2 * p * r / (p + r) if p == p and r == r and p + r else float("nan")
            rows.append({"label": L, "tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f})
        cm = pd.crosstab(part["human_label"], part["pred_label"], rownames=["human"], colnames=["predicted"])
        errors = part[part["pred_label"] != part["human_label"]][["row_id", "LIKE", "DISLIKE", "human_label", "pred_label", "rule_ids"]]
        report[split] = {"n": len(part), "per_label": pd.DataFrame(rows), "confusion": cm, "errors": errors}
    return report
