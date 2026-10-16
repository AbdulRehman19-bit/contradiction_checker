# Flow

Living document. Describes **how the system works**, step by step. Updated whenever the pipeline changes.
(The *why* behind each choice lives in [decision_tree.md](decision_tree.md).)

_Last updated: 2026-10-16 — plan finalized, no code built yet._

## Core target (clarified by user)
The primary thing to catch is the **direct same-aspect contradiction**:
> Like: "I like the taste" / Dislike: "I don't like the taste"

Everything else (misplaced answers, hedged "nothing", tension) is secondary but cheap and valuable.

## Overall pipeline

```
read -> normalise -> clause split -> none-filter -> aspect extraction -> stance (polarity + negation)
      -> pairing (same aspect) -> rule matrix -> scoring -> output
```
(v2 adds: aspect clustering + parent/child hierarchy, between stance and pairing.)

## Phased plan

| Phase | Scope | Gate |
|-------|-------|------|
| 0 | Environment check (Python, spaCy model, NLTK data on Windows); profile the 300 rows, verify the 25% none-ish / ~35 overlap assumptions | report to user |
| 1 (v1) | io, normalise, segment, nonefilter, basic aspects (lemma-equality match), stance with negation, rules for: **direct same-aspect contradiction**, NO_COMPLAINT, NO_DATA, SELF_CONFLICT, MISPLACED_POSITIVE/NEGATIVE, BARE_ASPECT_CONFLICT; xlsx/jsonl output; CLI; tests | interim summary to user |
| 2 | Gold template (stratified by rule candidate, not random) -> **user labels** -> dev/test evaluation with confidence intervals | needs user labels |
| 3 (v2) | Aspect clustering (YAML hierarchy first, WordNet second, rapidfuzz), PARENT_CHILD/SIBLING, TENSION, excess/deficit/balanced markers, confidence calibration | after gold results |
| 4 | Theme-code adapter, `--explain`, README, different-domain fixtures | done |
| UI | Streamlit frontend (`app/streamlit_app.py`): upload file, pick sheet/columns, edit YAML lexicons live, run, filter/review results, download xlsx. Built right after Phase 1 so v1 results are visible | after Phase 1 |

## Data profile (Phase 0, `data/File for uploading 1.xlsx`, Sheet1)
- 300 rows, 2 columns (LIKE / DISLIKE `- value`), 2 blank Dislike cells -> `NO_DATA`.
- Dislike starts with a none-phrase: 75 rows (25%), matches the spec.
- Rows sharing a content word across fields: 52 (spec estimated ~35; depends on stopword list).
- Median length: Like 9 words, Dislike 6 words.
- Observation: few literal "I like X / I don't like X" pairs. Real conflicts are subtler: e.g. Like "white chocolate center is very good" vs Dislike "can't taste the speculoos"; Like "speculoos flavor" vs Dislike "white chocolate taste fades into the background"; Like "mild taste, balanced" vs Dislike "white chocolate barely detectable". Negation-on-same-aspect and presence/absence markers (barely, can't taste, fades) are therefore needed in v1, not only v3.

## Folder layout
```
data/        <- PUT YOUR INPUT FILE HERE (git-ignored)
contra/      <- engine (config/ holds all YAML lexicons)
app/         <- Streamlit frontend
tests/       <- pytest
output/      <- results (git-ignored)
```

## Environment (Phase 0 result)
Python 3.11.9, `.venv` created. Installed: pandas, openpyxl, spaCy + `en_core_web_sm`, NLTK + WordNet, rapidfuzz, scikit-learn, pytest, PyYAML, streamlit. Nothing degraded.

## Stages

| # | Stage | Module | Input -> Output | Phase | Status |
|---|-------|--------|-----------------|-------|--------|
| 1 | Ingest | `io.py` | xlsx/csv -> DataFrame (+ auto-detect columns) | 1 | done |
| 2 | Normalise | `normalise.py` | text -> cleaned text + offsets (typo fix not built yet, off by default) | 1 | done |
| 3 | Clause split | `segment.py` | text -> clauses with offsets | 1 | done |
| 4 | None detector | `nonefilter.py` | answer -> NONE / HEDGED_NONE / NODATA / CONTENT | 1 | done |
| 5 | Aspect extraction | `aspects.py` | clause -> head + phrase | 1 | not started |
| 6 | Stance | `stance.py` | clause -> polarity, negation, strength | 1 (basic) / 3 (full) | not started |
| 7 | Clustering | `cluster.py` | aspects -> groups + hierarchy | 3 | not started |
| 8 | Pairing + rules | `rules.py` | stances -> label | 1 / 3 | not started |
| 9 | Scoring | `score.py` | -> confidence/bucket (calibrated on gold) | 1 / 3 | not started |
| 10 | Output | `report.py` | -> Results/Review/Summary/Aspects + jsonl | 1 | not started |

## Direct-contradiction flow (v1 core)
1. Split Like and Dislike into clauses.
2. For each clause: aspect head (e.g. `taste`) + polarity, using field prior then negation/sentiment words.
   - "I like the taste" in Like -> (taste, +)
   - "I don't like the taste" in Dislike -> (taste, -)  (negation flips "like")
3. Match aspects across fields (same lemma in v1; clusters in v3).
4. Like `+` vs Dislike `-` on the same aspect with a specific claim -> `CONTRADICTION`.
   Bare aspect on both sides -> `BARE_ASPECT_CONFLICT`.
5. Same-direction complaints (both say "too sweet") -> not a contradiction.

## Change log

- 2026-10-16: File created.
- 2026-10-16: Built config loader, io, normalise, segment, nonefilter + 38 tests. On the 300-row sample the Dislike column splits into NONE 79, CONTENT 217, HEDGED_NONE 2, NODATA 2.
- 2026-10-16: Plan finalized; phases added; direct same-aspect contradiction made the core target.
