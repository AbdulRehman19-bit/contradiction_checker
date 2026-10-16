import pandas as pd

from contra import analyze_dataframe
from contra.gold import evaluate, write_gold_template


def test_template_and_evaluate(tmp_path, cfg):
    df = pd.DataFrame({"LIKE": ["I like the taste", "Good", "Crunchy"] * 6, "DISLIKE": ["I do not like the taste", "Nothing", "Too sweet"] * 6})
    out = analyze_dataframe(df, "LIKE", "DISLIKE", cfg)
    path = write_gold_template(out, "LIKE", "DISLIKE", tmp_path / "g.xlsx")
    lab = pd.read_excel(path, sheet_name="Label")
    assert "pred_label" not in lab.columns and (lab["human_label"].isna() | (lab["human_label"] == "")).all()
    pred = pd.read_excel(path, sheet_name="Predictions")
    lab["human_label"] = pred["pred_label"]          # perfect labeller
    with pd.ExcelWriter(path) as xw:
        lab.to_excel(xw, sheet_name="Label", index=False)
        pred.to_excel(xw, sheet_name="Predictions", index=False)
    rep = evaluate(path)
    assert rep["all"]["n"] == len(lab)
    assert rep["all"]["errors"].empty
