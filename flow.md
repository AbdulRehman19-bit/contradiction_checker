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
| 5 | Aspect extraction | `aspects.py` | clause -> noun set (head + noun modifiers, "X of Y" folded), adjective->attribute, bare flag | 1 | done |
| 6 | Stance | `stance.py` | clause -> polarity, direction, strength (prior -> markers -> negation -> intensity -> mixed check) | 1 | done |
| 7 | Clustering | `cluster.py` | aspects -> groups (v1 uses alias map + small YAML hierarchy instead) | 3 | not started |
| 8 | Pairing + rules | `rules.py` | stances -> label | 1 | done |
| 9 | Scoring | `engine.py` (weights.yaml) | -> confidence/bucket; calibration on gold still to do | 1 / 3 | done (uncalibrated) |
| 10 | Output | `report.py`, `cli.py`, `engine.py` | -> Results/Review/Summary/Aspects xlsx + jsonl; `--explain ROW` | 1 | done |

## Pair outcome table (v1, in `rules._pair_outcome`)
| Aspect relation | Like | Dislike | Result |
|---|---|---|---|
| SAME | POS / PRESENT / BALANCED (explicit, strength >= 0.5) | NEG / ABSENT (explicit, not mixed) | CONTRADICTION |
| PARENT_CHILD or weak | same | NEG / ABSENT | TENSION |
| any | POS side | EXCESS / DEFICIT | TENSION |
| SAME | bare aspect | bare aspect | BARE_ASPECT_CONFLICT |
| PARENT_CHILD | bare | bare | TENSION |
| SAME | implicit (prior only) | explicit | TENSION (low) |
| SIBLING / UNRELATED | any | any | no finding |
Single-side rules: Dislike HEDGED_NONE -> SELF_CONFLICT; Dislike NONE + explicit praise -> MISPLACED_POSITIVE else NO_COMPLAINT; Like clause with explicit complaint -> MISPLACED_NEGATIVE.

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
- 2026-10-16: Built aspects, stance, rules, engine, report, CLI. 64 tests pass. Sample result: CONSISTENT 173, NO_COMPLAINT 76, TENSION 32, MISPLACED_POSITIVE 10, MISPLACED_NEGATIVE 5, SELF_CONFLICT 2, NO_DATA 2, CONTRADICTION 0. Run takes ~11 s.
- 2026-10-16: Plan finalized; phases added; direct same-aspect contradiction made the core target.
- 2026-10-16: Added `app/streamlit_app.py` (upload or pick from data/, sheet + column pickers, live YAML lexicon editor, product-word box, label/confidence/search filters, row click -> full parse trace, xlsx download). Run: `.\.venv\Scripts\streamlit run app/streamlit_app.py`.
- 2026-10-16: Added `contra/gold.py`: `--gold-template XLSX` writes a stratified, blind labelling sheet (sheets: Label with dropdown, Guide, Predictions) with a fixed dev/test split; `--evaluate XLSX` prints per-label precision/recall/F1, confusion matrix and errors for dev, test, all. The Streamlit YAML editor moved into a collapsed "Advanced" expander.
- 2026-10-16: Colour coding. `contra/config/colors.yaml` maps every label to a fill / strong colour and a plain-language meaning. Excel report: rows tinted by label, bold coloured Label cell, frozen header, auto-filter, new `Legend` sheet. Streamlit: analysis starts automatically when a file/columns/rules change (no Run button); first view = all rows colour-coded; filters are `Show` (All rows / Only rows to review / Pick findings), `How sure is the system?` (Any / Medium or higher / High only) and a text search; word-list editor lives under "Advanced options".
- 2026-10-16: Gold labels received (90 rows, 46 dev / 44 test). Rules tuned on dev only (see D21). Dev accuracy 0.98 (optimistic), test accuracy 0.70. Sample run now: CONSISTENT 170, NO_COMPLAINT 81, MISPLACED_POSITIVE 21, TENSION 18, MISPLACED_NEGATIVE 5, SELF_CONFLICT 2, CONTRADICTION 2, NO_DATA 1.
- 2026-10-16: Fresh multi-domain set (`output/fresh_test_rows.xlsx`, 102 rows with labels) scored 51% before changes, 77% after (see D22). New modules: `lexicon.py` (VADER + WordNet antonyms), `config/antonyms.yaml`. New rules: antonym predicates, negated shared predicate, bare/bare identical words, `@overall` verdicts, partial-scope downgrade, "except X" clauses, scoped "nothing wrong with X". 87 tests pass. Original gold: dev 0.98, test 0.73.
- 2026-10-16: Hard trap set added (see D23). 42% untouched -> 58% overall after tuning (even 0.69, odd 0.47 held-out). Fresh multi-domain set 0.78. Original gold dev 0.98 / test 0.73. 87 tests pass.
