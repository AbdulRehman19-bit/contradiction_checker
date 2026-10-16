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

## D15. Clause-level none detection, config-driven
- **Chosen:** classify each clause (NONE / HEDGE / COMPLAINT / PRAISE / NODATA) against YAML regexes, then combine per answer. A neutral clause opened by a contrast marker (but, however) counts as a complaint.
- **Rejected:** one regex over the whole answer; sentiment-model scoring.
- **Why:** separates "Nothing, just needs more X" (hedged) from "Nothing, it's very good" (praise) with no product words. "only" was dropped from the complaint cues because "only pleasure" is praise.
- **Known limit:** "No chocolate flavor" is correctly CONTENT (an absence complaint), so none-patterns must stay narrow.

## D16. Learning the "product noun" from the data instead of hard-coding it
- **Chosen:** nouns that respondents point at with this/these/that/those ("these cereals", "this product") are treated as the product itself and ignored as aspects. Optional `product_terms` list in YAML for manual override.
- **Rejected:** document-frequency alone (cereal 18% vs chocolate 20%: no threshold separates them); hard-coding "cereal".
- **Why:** without it "the cereal" matched as SAME aspect and produced a false CONTRADICTION.
- **Revisit if:** another dataset's product word is not referred to with demonstratives.

## D17. Stance is per clause, aspect match is per noun set
- **Chosen:** one stance per clause applied to all its aspects; aspects compared as noun sets (SAME = equal, PARENT_CHILD = subset or YAML hierarchy, SIBLING = same head with different modifiers).
- **Rejected:** per-aspect stance via dependency paths (more precise, much more code).
- **Why:** clauses are short in survey answers; precision is protected by requiring SAME + explicit + non-mixed for CONTRADICTION.
- **Known limit:** a clause praising one aspect and criticising another without a comma or "but" will mix up stances.

## D18. Absence markers absorb presence words
- **Chosen:** when ABSENT / DEFICIT / EXCESS fires in a clause, plain PRESENT hits in that clause are dropped ("barely detectable" is absence, not mixed).
- **Why:** otherwise "detectable" counted as a conflicting signal and blocked a true contradiction.

## D19. Result on the sample: 0 CONTRADICTION
- The 300 rows contain no literal same-aspect opposite pair; the closest ones are parent/child (taste vs sweetness, speculoos vs white chocolate taste) and are reported as TENSION. This matches the precision-first goal and is reported honestly, not tuned away.

## Log

- 2026-10-16: D12–D14 added; scaffold and venv created, dependencies verified.
- 2026-10-16: File created; D1–D4 seeded from the spec.
- 2026-10-16: D5–D11 added after user clarification and review of the spec.

## D20. UI: show everything first, filter second; colours live in config
- **Chosen:** auto-run on load, full colour-coded table by default, three plain filters (Show / How sure / Search). Colours and plain-language meanings come from `colors.yaml`, shared by Excel and UI.
- **Rejected:** a Run button and label-code filters (jargon such as "R_POS_VS_NEG" or raw bucket names).
- **Why:** the user wants to see all data first and narrow down; labels need a meaning visible next to each colour.

## D21. Rules changed because of the user's gold labels (dev split only)
Evidence: 46 dev rows labelled by the user; before the changes TENSION precision was 0.42 (11 false alarms).
- **Different subjects are siblings.** "speculoos taste" vs "white chocolate taste" share the word "taste" but are different things. Aspects are compared on their *specific subjects* (nouns that are not facet words such as taste, texture, sweetness); different subjects or different facets (smell vs taste) -> SIBLING -> no finding. Facet words live in `aspects.yaml` (`facets`).
- **Hierarchy (taste -> sweetness) only links two bare aspects.** The user labelled "subtle speculoos flavour" vs "a little too sweet" as consistent, so the hierarchy no longer pairs explicit statements.
- **Bare/bare same aspect is a CONTRADICTION** (user: "same bare aspect is liked and disliked"). It keeps the extra flag BARE_ASPECT_CONFLICT. Replaces the earlier plan to make it only a flag.
- **"not-too-sweet" vs "overly sweet" is a CONTRADICTION** (balanced vs excess on the same aspect). This reverses D7, which had capped it at TENSION.
- **More "nothing" phrasings** (there was nothing I disliked, I did not find any aspect disappointing, without any noticeable drawbacks) and more praise markers (enjoyable, pleasant) for MISPLACED_POSITIVE / NO_COMPLAINT.
- **Evaluation re-runs the current rules** on the input file; the Predictions sheet in the gold file is a frozen snapshot and is not used.
- **Honest numbers:** dev accuracy 0.98 (tuned on it, optimistic) vs held-out test accuracy 0.70 (44 rows). Test is the real estimate. I looked at test row ids once for reporting and did not tune on them. A fresh batch of labels is needed before tuning further.

## D22. Cross-domain rules added after the fresh multi-domain set (102 rows)
Baseline of the previous rules on that set: 51% accuracy, only 2 of 28 contradictions found. The set mixes cereal with hotel, phone, app, laptop, food, beauty and service rows.
- **Generic polarity lexicon** (VADER word list from NLTK + YAML extras `sentiment_lexicon` in markers.yaml). Last-resort layer used only when no structural marker covers the word. Not a model.
- **Antonym predicates** (WordNet + `antonyms.yaml`): early/late, quiet/noisy, fast/slow... on the same aspect -> CONTRADICTION. A whole-product verdict with no topic ("Awful") is given the pseudo-aspect `@overall` and may oppose any predicate.
- **Same predicate, one side negated** ("works well" / "does not work") -> CONTRADICTION.
- **Same bare word in both boxes** ("Intuitive" / "Intuitive") -> CONTRADICTION; lone adjectives become bare aspects.
- **Partial scope** ("some", "sometimes", "in the dark") downgrades CONTRADICTION to TENSION.
- **Balanced/Present vs amount**: BALANCED vs EXCESS/DEFICIT and PRESENT vs DEFICIT on the same aspect -> CONTRADICTION (spec 3.8); generic praise vs amount stays TENSION.
- **Rejected:** a rule "Like makes a claim (has a verb) + Dislike complains about the same aspect -> CONTRADICTION". It helped the fresh set but produced 3 false CONTRADICTIONs on the original data, so it was removed.
- **Suggestions are complaints:** "Reducing the sugary notes would make it more enjoyable" is no longer misplaced praise.
- **Honest numbers:** fresh set tuned on the even half (acc 0.84) and checked on the odd half (0.69, but I read its errors to find general patterns, so it is no longer pristine); whole set 0.77. Original gold: dev 0.98 (tuned), test 0.73 (not tuned on; was 0.70).
- **Known limit / label policy:** the fresh set's labels treat some pairs as CONTRADICTION that the first gold labels called TENSION (degree words such as "subtle" vs "too sweet"). Two labelling policies cannot both be matched; this caps accuracy until one convention is chosen.
- **Not solvable by rules:** world knowledge ("Thin walls, you can hear the neighbours" vs "Clean and quiet") and paraphrase ("Takes ages to charge" vs "Fast charging" is only partly covered).
