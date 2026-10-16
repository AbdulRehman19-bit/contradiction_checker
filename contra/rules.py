"""Rule matrix: turns analysed Like/Dislike answers into candidate findings, then picks the primary label."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .aspects import ParsedClause, facet_words, relation
from .lexicon import are_antonyms
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


def _pair_outcome(sl: Stance, sd: Stance, rel: str, bare_l: bool, bare_d: bool, min_contra: float, l_claim: bool = False):
    """-> (label, rule_id) for one (like stance, dislike stance) with a related aspect, or None."""
    if bare_l and bare_d:      # the same bare word in both boxes: the field priors are opposite
        return ("CONTRADICTION", "R_BARE_BARE") if rel == "SAME" else ("TENSION", "R_BARE_PARENT_CHILD")
    if not (sl.polarity == "+" and sd.polarity == "-"):
        return None
    if not (sl.explicit and sd.explicit):
        return ("TENSION", "R_IMPLICIT_SIDE") if (rel == "SAME" or (rel == "PARENT_CHILD" and bare_l)) else None
    if sl.direction in POS_SIDE and sd.direction in {"NEG", "ABSENT"}:
        if rel == "SAME" and min(sl.strength, sd.strength) >= min_contra and not (sl.mixed or sd.mixed):
            return ("CONTRADICTION", "R_POS_VS_NEG" if sd.direction == "NEG" else "R_POS_VS_ABSENT")
        return ("TENSION", "R_POS_VS_NEG_WEAK")
    if sd.direction in {"EXCESS", "DEFICIT"}:
        # "not too sweet" vs "overly sweet": the Like side states the very thing the Dislike side denies
        if sl.direction == "BALANCED" and rel == "SAME" and min(sl.strength, sd.strength) >= min_contra:
            return ("CONTRADICTION", "R_BALANCED_VS_AMOUNT")
        if sl.direction == "PRESENT" and sd.direction == "DEFICIT" and rel == "SAME" and min(sl.strength, sd.strength) >= min_contra:
            return ("CONTRADICTION", "R_PRESENT_VS_DEFICIT")
        return ("TENSION", "R_POS_VS_AMOUNT")
    return None


def _partial(text: str, cfg: dict) -> bool:
    low = " " + text.lower() + " "
    return any(f" {m.lower()} " in low for m in cfg["markers"].get("partial_markers", []))


def _specific(aspects, facets: frozenset) -> set:
    return {n for a in aspects for n in a.nouns if n not in facets and not n.startswith("@")}


def _subject_set(ca: ClauseAnalysis, ans: AnswerAnalysis, facets: frozenset) -> set:
    """Specific subjects (speculoos, chocolate...) of a clause; falls back to the whole answer when the clause names none."""
    s = _specific(ca.parsed.aspects, facets)
    return s or _specific([a for c in ans.clauses for a in c.parsed.aspects], facets)


def _refine(rel: str, la, da, sl: set, sd: set, facets: frozenset) -> str:
    """Refine the noun-set relation with subjects and facets.
    1. different facets (smell vs taste) -> siblings;
    2. aspects that both name a specific subject are compared on those subjects (cinnamon vs speculoos -> siblings);
    3. otherwise the subjects of the surrounding clause / answer decide (speculoos vs white chocolate -> siblings)."""
    if rel == "UNRELATED":
        return rel
    fa, fb = la.nouns & facets, da.nouns & facets
    if fa and fb and fa.isdisjoint(fb) and not (la.bare and da.bare):   # bare taste/sugar pairs stay linked by the hierarchy
        return "SIBLING"
    sa, sb = la.nouns - facets, da.nouns - facets
    if sa and sb:
        return "SIBLING" if sa.isdisjoint(sb) else ("SAME" if rel == "SAME" else "PARENT_CHILD")
    if sl and sd:
        if sl.isdisjoint(sd):
            return "SIBLING"
        return "SAME" if rel == "SAME" else "PARENT_CHILD"
    return rel


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
        praise_ev = dis.text
        if any(p.search(praise_ev) for p in pos_markers):
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
    facets = facet_words(cfg)
    dis_has_praise = any(c.stance.explicit and c.stance.polarity == "+" for c in dis.clauses)
    if dk.kind in {CONTENT, HEDGED_NONE}:
        for lc in like.clauses:
            l_bare = bool(lc.parsed.aspects) and all(a.bare for a in lc.parsed.aspects)
            if (lc.stance.polarity != "+" and not l_bare) or lc.kind in {"NONE", "NODATA", "HEDGE"}:
                continue
            for dc in dis.clauses:
                d_bare = bool(dc.parsed.aspects) and all(a.bare for a in dc.parsed.aspects)
                if (dc.stance.polarity != "-" and not d_bare) or dc.kind in {"NONE", "NODATA", "HEDGE"}:
                    continue
                if dis_has_praise and not dc.stance.explicit:
                    continue    # bare/prior-only clause inside an answer that is really praise
                sl_set, sd_set = _subject_set(lc, like, facets), _subject_set(dc, dis, facets)
                for la in lc.parsed.aspects:
                    for da in dc.parsed.aspects:
                        rel = relation(la, da, cfg, allow_hierarchy=la.bare and da.bare)
                        rel = _refine(rel, la, da, sl_set, sd_set, facets)
                        wild = "@overall" in la.nouns or "@overall" in da.nouns       # a whole-product verdict can oppose any predicate
                        anto = (rel == "SAME" or wild) and any(are_antonyms(p, q, cfg) for p in lc.parsed.predicates for q in dc.parsed.predicates)
                        if rel in {"SIBLING", "UNRELATED"} and not anto:
                            continue
                        out = _pair_outcome(lc.stance, dc.stance, rel, la.bare, da.bare, min_contra,
                                            l_claim=bool(lc.parsed.has_verb)) if rel not in {"SIBLING", "UNRELATED"} else None
                        shared = set(lc.parsed.predicates) & set(dc.parsed.predicates)
                        if rel == "SAME" and shared and lc.parsed.negated != dc.parsed.negated:
                            out = ("CONTRADICTION", "R_NEGATED_PREDICATE")     # "works well" / "does not work"
                        if anto:
                            out = ("CONTRADICTION", "R_ANTONYM")
                        if out and out[0] == "CONTRADICTION" and _partial(dc.clause.text, cfg):
                            out = ("TENSION", out[1] + "_PARTIAL")             # "sometimes", "some of the..."
                        if out is None:
                            continue
                        label, rule = out
                        base = {"R_BARE_BARE": 0.7, "R_ANTONYM": 0.75, "R_NEGATED_PREDICATE": 0.7, "R_CLAIM_VS_NEG": 0.5}.get(rule, min(lc.stance.strength, dc.stance.strength))
                        strength = base * w["relation_weight"].get(rel, 1.0) if rel not in {"SIBLING", "UNRELATED"} else base
                        cands.append(Candidate(label, rule, strength, rel, aspect=la.head if rel == "SAME" else f"{la.head}~{da.head}",
                                               like_ev=lc.clause.text, dislike_ev=dc.clause.text,
                                               stances={"like": lc.stance.rule_id, "dislike": dc.stance.rule_id}))
    default = "NO_COMPLAINT" if dk.kind == NONE else "CONSISTENT"
    return cands, default
