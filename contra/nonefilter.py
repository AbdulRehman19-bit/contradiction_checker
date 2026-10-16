"""None detector: classify a whole answer as NONE / HEDGED_NONE / NODATA / CONTENT. Config-driven."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .normalise import expand_contractions, normalise
from .segment import Clause, split_clauses

NONE, HEDGED_NONE, NODATA, CONTENT = "NONE", "HEDGED_NONE", "NODATA", "CONTENT"


@dataclass
class NoneResult:
    kind: str
    has_praise: bool = False
    hedge_reason: str | None = None       # "complaint_after_none" | "hedge_phrase"
    none_clause: str | None = None
    complaint_clauses: list[str] = field(default_factory=list)
    praise_clauses: list[str] = field(default_factory=list)
    low_conf_lang: bool = False
    rule_id: str = ""


def _prep(clause_text: str, cfg: dict) -> str:
    """Lower-case, expand contractions, strip punctuation and filler words at the clause edges."""
    t = expand_contractions(clause_text, cfg)
    t = re.sub(r"[^\w\s/'-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    fillers = sorted(cfg["none_patterns"].get("fillers", []), key=len, reverse=True)
    changed = True
    while changed and t:
        changed = False
        for f in fillers:
            if t.startswith(f + " "):
                t, changed = t[len(f) + 1:], True
            elif t.endswith(" " + f):
                t, changed = t[: -len(f) - 1], True
            elif t == f:
                t, changed = "", True
    return t.strip()


def _full(patterns: list[str], t: str) -> bool:
    return any(re.fullmatch(p, t) for p in patterns)


def classify_clause(clause: Clause, cfg: dict) -> str:
    """-> 'NODATA' | 'HEDGE' | 'NONE' | 'COMPLAINT' | 'PRAISE' | 'OTHER'"""
    np_cfg = cfg["none_patterns"]
    t = _prep(clause.text, cfg)
    if not t:
        return "OTHER"
    if _full(np_cfg["nodata_patterns"], t):
        return "NODATA"
    if _full(np_cfg["hedge_none_patterns"], t):
        return "HEDGE"
    if _full(np_cfg.get("scoped_none_patterns", []), t):
        return "PRAISE"      # "nothing wrong with the taste": praise about one thing, not a blanket "no complaints"
    if _full(np_cfg["none_patterns"], t):
        return "NONE"
    words = set(t.split())
    complaint_vocab = {w.lower() for w in np_cfg["complaint_cues"]}
    praise_vocab = {w.lower() for w in np_cfg["praise_cues"]}
    if (words & complaint_vocab) or "not" in words:
        return "COMPLAINT"
    return "PRAISE" if words & praise_vocab else "OTHER"


def detect_none(value, cfg: dict) -> NoneResult:
    norm = normalise(value, cfg)
    if norm.is_empty:
        return NoneResult(NODATA, rule_id="NF_EMPTY")
    clauses = split_clauses(norm.text, cfg)
    kinds = []
    for c in clauses:
        k = classify_clause(c, cfg)
        # a neutral clause opened by a contrast marker ("..., but the battery drains") is a complaint
        if k == "OTHER" and c.marker:
            k = "COMPLAINT"
        kinds.append((c, k))
    labels = [k for _, k in kinds]
    praise = [c.text for c, k in kinds if k == "PRAISE"]
    complaints = [c.text for c, k in kinds if k == "COMPLAINT"]
    base = dict(low_conf_lang=norm.low_conf_lang, praise_clauses=praise, complaint_clauses=complaints)

    if labels and all(k == "NODATA" for k in labels):
        return NoneResult(NODATA, rule_id="NF_NODATA", **base)
    if "HEDGE" in labels:
        return NoneResult(HEDGED_NONE, hedge_reason="hedge_phrase", rule_id="NF_HEDGE_PHRASE",
                          none_clause=next(c.text for c, k in kinds if k == "HEDGE"), **base)
    if "NONE" in labels:
        none_clause = next(c.text for c, k in kinds if k == "NONE")
        if complaints:
            return NoneResult(HEDGED_NONE, hedge_reason="complaint_after_none", none_clause=none_clause,
                              rule_id="NF_HEDGED_NONE", **base)
        return NoneResult(NONE, has_praise=bool(praise), none_clause=none_clause,
                          rule_id="NF_NONE_PRAISE" if praise else "NF_NONE", **base)
    return NoneResult(CONTENT, rule_id="NF_CONTENT", **base)
