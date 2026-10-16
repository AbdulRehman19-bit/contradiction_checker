# Contradiction checker

Rule-based (no LLM) detector for Like vs Dislike survey answers. See `flow.md` (how it works) and `decision_tree.md` (why).

## Run
```
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt && .venv\Scripts\python -m spacy download en_core_web_sm
.venv\Scripts\streamlit run app/streamlit_app.py          # UI
.venv\Scripts\python -m contra --input data/FILE.xlsx --sheet Sheet1 --out output/results.xlsx   # CLI
.venv\Scripts\python -m contra --input data/FILE.xlsx --sheet Sheet1 --explain 205                # trace one row
.venv\Scripts\python -m pytest -q
```
Put survey files in `data/` (git-ignored). All word lists live in `contra/config/*.yaml`.
