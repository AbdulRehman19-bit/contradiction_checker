# Decision Tree

Living document. Records **why** each approach was chosen over the alternatives.
(The *how* lives in [flow.md](flow.md).)

Format per decision: **Chosen -> Rejected -> Why -> Revisit if**.

_Last updated: 2026-10-16_

## D1. Rule-based vs LLM / neural
- **Chosen:** rule-based, deterministic, YAML-configured.
- **Rejected:** LLMs, transformer encoders (static vectors only behind an off-by-default flag).
- **Why:** hard constraint from user; every flag needs evidence phrase + rule id.
- **Revisit if:** user approves neural encoders.

## D2. Where aspects come from
- **Chosen:** learned per run from the data; only generic linguistic resources hard-coded.
- **Rejected:** hand-written cereal/chocolate aspect list.
- **Why:** must generalise to other products/surveys.

## D3. Stance: lexicon-only vs layered
- **Chosen:** layered (field prior -> markers -> negation -> intensity -> hedge), lexicon last.
- **Rejected:** general sentiment lexicon alone.
- **Why:** "sweet", "mild", "rich" flip with context; the field itself is strong signal.

## D4. Precision vs recall on CONTRADICTION
- **Chosen:** favour precision.
- **Why:** over-producing CONTRADICTION swamps review.

## D5. Core target = direct same-aspect contradiction (user clarification)
- **Chosen:** make "I like the taste" vs "I don't like the taste" the primary, highest-confidence case; build negation handling and same-aspect matching first.
- **Rejected:** treating nuanced excess/deficit/balanced cases as the main contradiction type.
- **Why:** this is what the user means by contradiction. Nuanced cases are lower-confidence and go to TENSION.

## D6. Phased build (v1 first)
- **Chosen:** v1 = none-filter, misplaced/self-conflict, direct contradiction; v2 = clustering/hierarchy/TENSION.
- **Rejected:** build everything in one pass.
- **Why:** v1 covers most of the value; clustering is the riskiest part and needs gold data to tune.

## D7. Balanced-vs-excess ("balanced sweetness" / "toned down") capped at TENSION
- **Chosen:** TENSION unless the like clause makes an explicit specific claim.
- **Rejected:** the spec's medium-confidence CONTRADICTION.
- **Why:** conflicts with precision-first; the two statements are not literally opposite.
- **Revisit if:** gold labels show reviewers consider these true contradictions.

## D8. Gold set stratified by rule candidate
- **Chosen:** oversample rows where a rule fired or aspects overlap, plus random controls.
- **Rejected:** pure random sample.
- **Why:** true contradictions are rare; random ~100 rows may hold only a few.
- **Note:** report confidence intervals, not bare P/R.

## D9. Confidence is calibrated, not assumed
- **Chosen:** start with spec formula, then calibrate buckets against gold labels.
- **Why:** min(strength)*weights is untested.

## D10. Hierarchy source order: YAML first, WordNet second
- **Chosen:** curated YAML hierarchy takes priority.
- **Rejected:** WordNet hypernyms as primary.
- **Why:** WordNet is noisy for survey vocabulary.

## D11. Typo correction off by default
- **Chosen:** symspell optional, every correction logged, protect corpus-frequent words.
- **Rejected:** always-on correction.
- **Why:** can "fix" product terms and break matching.

## D12. Which models (user question)
- **Chosen:** only `spaCy en_core_web_sm` (small statistical dependency parser/POS tagger, ~12 MB, not generative) + NLTK WordNet (a lexicon, not a model) + rapidfuzz (string matching).
- **Optional, off by default:** `en_core_web_md` static word vectors for synonym matching.
- **Rejected:** LLMs, transformers/sentence-embeddings (violates constraint; also less explainable).
- **Why:** parser is needed for negation scope and noun/adjective relations; everything else is rules.

## D13. "Dynamic, nothing hard-coded"
- **Chosen:** (a) aspects learned from each dataset; (b) columns/sheet chosen at runtime; (c) every linguistic list (negations, markers, none-phrases, antonyms, hierarchy) lives in YAML and is editable in the Streamlit UI without code changes; (d) no product words anywhere in code.
- **Honest limit:** generic English words like "not" or "too" must exist somewhere; they live in editable YAML defaults, not in code.
- **Rejected:** literals in Python.

## D14. Streamlit frontend
- **Chosen:** thin UI over the same `analyze_dataframe` API the CLI uses.
- **Why:** one engine, two front ends; no logic duplicated in the UI.

## Log

- 2026-10-16: D12–D14 added; scaffold and venv created, dependencies verified.
- 2026-10-16: File created; D1–D4 seeded from the spec.
- 2026-10-16: D5–D11 added after user clarification and review of the spec.
