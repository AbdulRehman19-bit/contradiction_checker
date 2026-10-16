"""Stance assignment for one clause: field prior -> explicit markers -> negation -> intensity -> mixed-signal check."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .lexicon import poltable
from .normalise import expand_contractions

POSITIVE = {"POS", "PRESENT", "BALANCED"}
NEGATIVE = {"NEG", "ABSENT", "EXCESS", "DEFICIT"}
# markers that out-rank plain polarity words when both fire in one clause
STRUCTURAL = {"ABSENT", "DEFICIT", "EXCESS", "BALANCED"}


@dataclass
class Stance:
    polarity: str               # '+', '-' or '0'
    direction: str              # POS NEG PRESENT ABSENT EXCESS DEFICIT BALANCED PRIOR
    strength: float
    evidence: str               # the matched phrase (in the lower-cased matching form)
    rule_id: str
    negated: bool = False
    mixed: bool = False
    hits: list[str] = field(default_factory=list)

    @property
    def explicit(self) -> bool:
        return self.direction != "PRIOR"


def _hits(text: str, markers: list[dict]) -> list[dict]:
    found = []
    for m in markers:
        for pat in m["patterns"]:
            for mt in re.finditer(pat, text):
                found.append({"id": m["id"], "direction": m["direction"], "weight": m["weight"],
                              "negatable": m.get("negatable", True), "start": mt.start(), "end": mt.end(),
                              "text": mt.group(0)})
    # keep the longest of any overlapping hits; earlier-listed (more specific) marker wins ties
    found.sort(key=lambda h: (-(h["end"] - h["start"]), h["start"]))
    kept: list[dict] = []
    for h in found:
        if not any(h["start"] < k["end"] and k["start"] < h["end"] for k in kept):
            kept.append(h)
    return sorted(kept, key=lambda h: h["start"])


def _lexicon_hits(text: str, taken: list[dict], cfg: dict) -> list[dict]:
    """Single words with a generic polarity (VADER + YAML extras) that no structural marker already covers."""
    table = poltable(cfg)
    out = []
    for m in re.finditer(r"[a-z]+", text):
        v = table.get(m.group(0))
        if v is None or any(m.start() < k["end"] and k["start"] < m.end() for k in taken):
            continue
        out.append({"id": "LEX", "direction": "POS" if v > 0 else "NEG", "weight": abs(v), "negatable": True,
                    "start": m.start(), "end": m.end(), "text": m.group(0)})
    return out


def _prev_words(text: str, pos: int, n: int) -> list[str]:
    return re.findall(r"[a-z']+", text[:pos])[-n:]


def assign_stance(clause_text: str, field_name: str, cfg: dict) -> Stance:
    """field_name: 'like' or 'dislike' (sets the prior)."""
    mk = cfg["markers"]
    text = expand_contractions(clause_text, cfg)
    prior_pol = "+" if field_name == "like" else "-"
    hits = _hits(text, mk["markers"])
    hits = sorted(hits + _lexicon_hits(text, hits, cfg), key=lambda h: h["start"])
    negators = set(mk["negators"])
    window = mk.get("negation_window_words", 3)
    flipped = []
    for h in hits:
        direction, weight, negated = h["direction"], h["weight"], False
        prev = _prev_words(text, h["start"], window)
        # a negator inside the matched phrase itself (e.g. "not to my liking") is part of the marker
        prev_text = " ".join(prev)
        if h["negatable"] and any(re.search(r"\b" + re.escape(n) + r"\b", prev_text) for n in negators):
            new, mult = mk["negation_flip"][direction]
            direction, weight, negated = new, weight * mult, True
        prev2 = _prev_words(text, h["start"], 2)
        joined = " ".join(prev2)
        if any(d in joined for d in mk["downtoners"]):
            weight *= mk["downtoner_multiplier"]
        elif any(i in prev2 for i in mk["intensifiers"]):
            weight = min(1.0, weight * mk["intensifier_multiplier"])
        flipped.append({**h, "direction": direction, "weight": min(1.0, weight), "negated": negated})

    if not flipped:
        return Stance(prior_pol, "PRIOR", mk["prior_strength"], clause_text, "ST_PRIOR_" + field_name.upper())

    # excess implies presence: drop plain PRESENT when an EXCESS marker is in the same clause
    # "barely detectable" / "not enough": the absence marker absorbs the presence word it modifies
    if any(h["direction"] in {"EXCESS", "ABSENT", "DEFICIT"} for h in flipped):
        flipped = [h for h in flipped if h["direction"] != "PRESENT"] or flipped
    structural = [h for h in flipped if h["direction"] in STRUCTURAL]
    pool = structural or flipped
    top = max(pool, key=lambda h: h["weight"])
    pol = "+" if top["direction"] in POSITIVE else "-"
    strength = top["weight"]
    mixed = any(("+" if h["direction"] in POSITIVE else "-") != pol for h in flipped)
    if mixed:
        strength *= 0.7
    return Stance(pol, top["direction"], round(strength, 3), top["text"].strip(), f"ST_{top['id']}",
                  negated=top["negated"], mixed=mixed, hits=[f"{h['id']}:{h['text'].strip()}" for h in flipped])
