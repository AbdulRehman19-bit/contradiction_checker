"""Rule matrix: turns analysed Like/Dislike answers into candidate findings, then picks the primary label."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .aspects import ParsedClause, relation
from .nonefilter import CONTENT, HEDGED_NONE, NODATA, NONE, NoneResult
from .segment import Clause
from .stance import Stance

POS_SIDE = {"POS", "PRESENT", "BALANCED"}


@dataclass
class ClauseAnalysis:
    clause: Clause
    parsed: ParsedClause
    stance: Stance
    kind: str = "OTHER"          # none-filter class of this clause


@dataclass
class AnswerAnalysis:
    text: str
    none: NoneResult
    clauses: list[ClauseAnalysis] = field(default_factory=list)


@dataclass
class Candidate:
    label: str
    rule_id: str
    strength: float
    relation: str | None = None
    aspect: str = ""
    like_ev: str = ""
    dislike_ev: str = ""
    stances: dict = field(default_factory=dict)


def _pair_outcome(sl: Stance, sd: Stance, rel: str, bare_l: bool, bare_d: bool, min_contra: float):
    """-> (label, rule_id) for one (like stance, dislike stance) with a related aspect, or None."""
    if not (sl.polarity == "+" and sd.polarity == "-"):
        return None
    if bare_l and bare_d:
        return ("BARE_ASPECT_CONFLICT", "R_BARE_BARE") if rel == "SAME" else ("TENSION", "R_BARE_PARENT_CHILD")
    if not (sl.explicit and sd.explicit):
        return ("TENSION", "R_IMPLICIT_SIDE") if rel == "SAME" else None
    if sl.direction in POS_SIDE and sd.direction in {"NEG", "ABSENT"}:
        if rel == "SAME" and min(sl.strength, sd.strength) >= min_contra and not (sl.mixed or sd.mixed):
            return ("CONTRADICTION", "R_POS_VS_NEG" if sd.direction == "NEG" else "R_POS_VS_ABSENT")
        return ("TENSION", "R_POS_VS_NEG_WEAK")
    if sd.direction in {"EXCESS", "DEFICIT"}:
        return ("TENSION", "R_POS_VS_AMOUNT")
    return None


def decide(like: AnswerAnalysis, dis: AnswerAnalysis, cfg: dict) -> tuple[list[Candidate], str]:
    """Return (candidates, default_label) — the caller picks the primary by severity."""
    w = cfg["weights"]
    min_contra = w["min_contradiction_strength"]
    cands: list[Candidate] = []

    if like.none.kind == NODATA or dis.none.kind == NODATA:
        return [Candidate("NO_DATA", "R_NODATA", 1.0)], "NO_DATA"

    # ---- Dislike side: none / hedged-none / misplaced praise ----
    dk = dis.none
    pos_markers = [re.compile(p, re.I) for p in cfg["markers"]["misplaced_positive_markers"]]
    if dk.kind == HEDGED_NONE:
        s = 0.9 if dk.hedge_reason == "complaint_after_none" else 0.4
        ev = " / ".join(dk.complaint_clauses) or dis.text
        cands.append(Candidate("SELF_CONFLICT", "R_SELF_CONFLICT_" + (dk.hedge_reason or "").upper(), s, dislike_ev=ev))
    elif dk.kind == NONE:
        praise_ev = " ".join(dk.praise_clauses)
        if dk.has_praise and any(p.search(praise_ev) for p in pos_markers):
            cands.append(Candidate("MISPLACED_POSITIVE", "R_MISPLACED_POS_NONE_PRAISE", 0.9, dislike_ev=dis.text))
        else:
            cands.append(Candidate("NO_COMPLAINT", "R_NO_COMPLAINT", 0.9, dislike_ev=dis.text))
    elif dk.kind == CONTENT:
        live = [c for c in dis.clauses if c.kind not in {"NONE", "NODATA", "HEDGE"}]
        praising = [c for c in live if c.stance.polarity == "+" and c.stance.explicit]
        # bare/prior-only clauses ("The taste,") inside an answer that also praises are not complaints
        complaining = [c for c in live if c.stance.polarity == "-" and (c.stance.explicit or (c.parsed.aspects and not praising))]
        if live and not complaining and praising and any(p.search(" ".join(c.clause.text for c in praising)) for p in pos_markers):
            cands.append(Candidate("MISPLACED_POSITIVE", "R_MISPLACED_POS_ALL_PRAISE", 0.8, dislike_ev=dis.text))

    # ---- Like side: complaint hiding in the Like answer ----
    for c in like.clauses:
        st = c.stance
        if st.explicit and st.polarity == "-" and st.strength >= 0.35 and c.kind not in {"NONE", "NODATA"}:
            cands.append(Candidate("MISPLACED_NEGATIVE", "R_MISPLACED_NEG", st.strength, like_ev=c.clause.text,
                                   stances={"like": st.rule_id}))
            break

    # ---- Pairing across fields ----
    dis_has_praise = any(c.stance.explicit and c.stance.polarity == "+" for c in dis.clauses)
    if dk.kind in {CONTENT, HEDGED_NONE}:
        for lc in like.clauses:
            if lc.stance.polarity != "+" or lc.kind in {"NONE", "NODATA", "HEDGE"}:
                continue
            for dc in dis.clauses:
                if dc.stance.polarity != "-" or dc.kind in {"NONE", "NODATA", "HEDGE"}:
                    continue
                if dis_has_praise and not dc.stance.explicit:
                    continue    # bare/prior-only clause inside an answer that is really praise
                for la in lc.parsed.aspects:
                    for da in dc.parsed.aspects:
                        rel = relation(la, da, cfg)
                        if rel in {"SIBLING", "UNRELATED"}:
                            continue
                        out = _pair_outcome(lc.stance, dc.stance, rel, la.bare, da.bare, min_contra)
                        if out is None:
                            continue
                        label, rule = out
                        strength = min(lc.stance.strength, dc.stance.strength) * w["relation_weight"][rel]
                        cands.append(Candidate(label, rule, strength, rel, aspect=la.head if rel == "SAME" else f"{la.head}~{da.head}",
                                               like_ev=lc.clause.text, dislike_ev=dc.clause.text,
                                               stances={"like": lc.stance.rule_id, "dislike": dc.stance.rule_id}))
    default = "NO_COMPLAINT" if dk.kind == NONE else "CONSISTENT"
    return cands, default
