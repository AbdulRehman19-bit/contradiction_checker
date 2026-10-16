"""Public API: analyze_pair / analyze_dataframe. Wires the pipeline stages together."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import pandas as pd

from .aspects import get_nlp, nlp_status, parse_clause
from .config import load_config
from .nonefilter import classify_clause, detect_none
from .normalise import normalise
from .rules import AnswerAnalysis, Candidate, ClauseAnalysis, decide
from .segment import split_clauses
from .stance import assign_stance


@dataclass
class PairResult:
    label: str
    extra_flags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    bucket: str = "LOW"
    aspect: str = ""
    like_evidence: str = ""
    dislike_evidence: str = ""
    rule_ids: list[str] = field(default_factory=list)
    explanation: str = ""
    stances: list[dict] = field(default_factory=list)
    like_none: str = ""
    dislike_none: str = ""
    lang_flag: bool = False


def analyze_answer(value, field_name: str, cfg: dict, extra_generic: frozenset = frozenset()) -> AnswerAnalysis:
    norm = normalise(value, cfg)
    none = detect_none(value, cfg)
    ans = AnswerAnalysis(text=norm.text, none=none)
    for cl in split_clauses(norm.text, cfg):
        kind = classify_clause(cl, cfg)
        if kind == "OTHER" and cl.marker:
            kind = "COMPLAINT"
        ans.clauses.append(ClauseAnalysis(cl, parse_clause(cl.text, cfg, extra_generic),
                                          assign_stance(cl.text, field_name, cfg), kind))
    return ans


def _bucket(conf: float, w: dict) -> str:
    return "HIGH" if conf >= w["buckets"]["high"] else "MED" if conf >= w["buckets"]["med"] else "LOW"


def analyze_pair(like, dislike, ctx: dict | None = None) -> PairResult:
    """ctx: {'cfg': config dict (default: load_config()), 'extra_generic': frozenset of corpus-generic nouns}"""
    ctx = ctx or {}
    cfg = ctx.get("cfg") or load_config()
    extra = ctx.get("extra_generic", frozenset())
    w = cfg["weights"]
    la = analyze_answer(like, "like", cfg, extra)
    da = analyze_answer(dislike, "dislike", cfg, extra)
    cands, default = decide(la, da, cfg)
    order = {lab: i for i, lab in enumerate(w["severity_order"])}
    real = list(cands)
    real.sort(key=lambda c: (order.get(c.label, 99), -c.strength))
    primary = real[0] if real else Candidate(default, "R_DEFAULT_" + default, 0.5)
    lang_flag = la.none.low_conf_lang or da.none.low_conf_lang
    rw = w["rule_weight"].get(primary.label, 0.6)
    if primary.label in {"CONTRADICTION", "TENSION", "BARE_ASPECT_CONFLICT", "MISPLACED_NEGATIVE", "SELF_CONFLICT"}:
        conf = primary.strength * rw
    elif primary.label in {"MISPLACED_POSITIVE", "NO_COMPLAINT"}:
        conf = primary.strength * rw / 0.9 if primary.label == "NO_COMPLAINT" else primary.strength * rw
    else:
        conf = primary.strength
    if lang_flag:
        conf *= w["lang_penalty"]
    conf = round(min(conf, 1.0), 3)
    extra_flags = sorted({c.label for c in cands if c.label != primary.label and c.label not in {"CONSISTENT"}} |
                         ({"BARE_ASPECT_CONFLICT"} - {primary.label} if any(c.label == "BARE_ASPECT_CONFLICT" for c in cands) else set()))
    if lang_flag:
        extra_flags.append("LOW_CONFIDENCE_LANG")
    tpl = cfg["templates"].get(primary.label, "")
    expl = tpl.format(aspect=primary.aspect or "-", like=primary.like_ev or la.text, dislike=primary.dislike_ev or da.text)
    return PairResult(
        label=primary.label, extra_flags=extra_flags, confidence=conf, bucket=_bucket(conf, w),
        aspect=primary.aspect, like_evidence=primary.like_ev, dislike_evidence=primary.dislike_ev,
        rule_ids=sorted({primary.rule_id, *[v for v in primary.stances.values()]}), explanation=expl,
        stances=[{"label": c.label, "rule": c.rule_id, "relation": c.relation, "aspect": c.aspect,
                  "strength": round(c.strength, 3), "like": c.like_ev, "dislike": c.dislike_ev} for c in real],
        like_none=la.none.kind, dislike_none=da.none.kind, lang_flag=lang_flag)


def fit_generic_nouns(texts: list[str], cfg: dict) -> frozenset:
    """Corpus-dependent non-aspect nouns, learned from the data (nothing product-specific is hard-coded):
    (1) nouns in >= generic_df_ratio of all answers; (2) nouns respondents point at with this/these/that/those
    ("this cereal", "these products") - that is how people refer to the product itself; (3) user product_terms."""
    a = cfg["aspects"]
    extra = {t.lower() for t in a.get("product_terms", []) or []}
    nlp = get_nlp()
    if nlp is None or not texts:
        return frozenset(extra)
    ratio, dem_min, dem_ratio = a.get("generic_df_ratio", 1.0), a.get("demonstrative_min_count", 4), a.get("demonstrative_ratio", 0.1)
    docs_with: Counter = Counter()
    total: Counter = Counter()
    dem: Counter = Counter()
    clean = [str(t) for t in texts if isinstance(t, str) and t.strip()]
    for doc in nlp.pipe(clean):
        seen = set()
        for t in doc:
            if t.pos_ in {"NOUN", "PROPN"}:
                k = t.lemma_.lower()
                seen.add(k)
                total[k] += 1
                if any(c.dep_ == "det" and c.lower_ in {"this", "these", "that", "those"} for c in t.children):
                    dem[k] += 1
        docs_with.update(seen)
    n = len(clean)
    extra |= {w for w, c in docs_with.items() if c / n >= ratio}
    extra |= {w for w in dem if dem[w] >= dem_min and dem[w] / total[w] >= dem_ratio}
    return frozenset(extra)


def analyze_dataframe(df: pd.DataFrame, like_col: str, dislike_col: str, config: dict | None = None) -> pd.DataFrame:
    """Returns a copy of df with result columns appended (original columns untouched)."""
    cfg = config or load_config()
    extra = fit_generic_nouns(list(df[like_col]) + list(df[dislike_col]), cfg)
    rows = []
    for like, dis in zip(df[like_col], df[dislike_col]):
        r = analyze_pair(like, dis, {"cfg": cfg, "extra_generic": extra})
        rows.append({
            "label": r.label, "extra_flags": ", ".join(r.extra_flags), "confidence": r.confidence, "bucket": r.bucket,
            "aspect": r.aspect, "like_evidence": r.like_evidence, "dislike_evidence": r.dislike_evidence,
            "rule_ids": ", ".join(r.rule_ids), "explanation": r.explanation,
            "like_none": r.like_none, "dislike_none": r.dislike_none, "_stances": r.stances})
    out = df.copy()
    res = pd.DataFrame(rows, index=df.index)
    for c in res.columns:
        out[c] = res[c]
    out.attrs["generic_nouns"] = sorted(extra)
    out.attrs["degraded"] = [m for m in [nlp_status()] if m]
    return out


def explain_pair(like, dislike, ctx: dict | None = None) -> str:
    """Human-readable trace of clauses, aspects, stances and fired rules for one pair (CLI --explain)."""
    ctx = ctx or {}
    cfg = ctx.get("cfg") or load_config()
    extra = ctx.get("extra_generic", frozenset())
    lines = []
    for name, val in (("LIKE", like), ("DISLIKE", dislike)):
        a = analyze_answer(val, name.lower(), cfg, extra)
        lines.append(f"{name}: {a.text!r}  none-filter={a.none.kind} ({a.none.rule_id})")
        for c in a.clauses:
            asp = ", ".join(f"{x.phrase}->{sorted(x.nouns)}{'(bare)' if x.bare else ''}" for x in c.parsed.aspects) or "-"
            s = c.stance
            lines.append(f"  [{c.clause.index}] {c.clause.text!r} kind={c.kind} marker={c.clause.marker}\n"
                         f"       aspects: {asp}\n"
                         f"       stance: {s.polarity} {s.direction} strength={s.strength} rule={s.rule_id} hits={s.hits}")
    r = analyze_pair(like, dislike, ctx)
    lines.append(f"RESULT: {r.label} conf={r.confidence} ({r.bucket}) flags={r.extra_flags} rules={r.rule_ids}")
    lines.append(f"  {r.explanation}")
    for s in r.stances:
        lines.append(f"  candidate: {s}")
    return "\n".join(lines)
