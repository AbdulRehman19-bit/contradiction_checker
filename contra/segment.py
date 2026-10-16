"""Clause segmentation. A clause is the unit for all later steps; offsets point into the normalised text."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Clause:
    text: str
    start: int
    end: int
    marker: str | None = None   # contrast marker that opened this clause (but/however/...)
    index: int = 0


def _boundaries(text: str, cfg: dict) -> list[tuple[int, int]]:
    """Return (start, end) spans of the separators to cut on."""
    seg = cfg["segment"]
    spans = []
    for pat in seg["split_patterns"]:
        spans += [m.span() for m in re.finditer(pat, text)]
    markers = "|".join(re.escape(m) for m in seg["contrast_markers"])
    # cut BEFORE a contrast marker (zero-width), marker stays with the next clause
    spans += [(m.start(), m.start()) for m in re.finditer(rf"\b(?:{markers})\b", text, re.I)]
    return sorted(spans)


def split_clauses(text: str, cfg: dict) -> list[Clause]:
    if not text:
        return []
    seg = cfg["segment"]
    markers = {m.lower() for m in seg["contrast_markers"]}
    connectors = {c.lower() for c in seg.get("connectors", [])}
    cuts, pos = [], 0
    for s, e in _boundaries(text, cfg):
        if s >= pos:
            cuts.append((pos, s))
            pos = e
    cuts.append((pos, len(text)))

    clauses: list[Clause] = []
    for s, e in cuts:
        raw = text[s:e]
        lead = len(raw) - len(raw.lstrip())
        body = raw.strip()
        if not body:
            continue
        start = s + lead
        marker = None
        words = body.split(" ")
        # strip leading connectors; note a contrast marker
        while words and words[0].lower().strip(",") in connectors | markers:
            w = words.pop(0)
            if w.lower().strip(",") in markers:
                marker = w.lower().strip(",")
            start = text.find(words[0], start) if words else start
        if not words:
            continue
        body = " ".join(words)
        clauses.append(Clause(text=body, start=start, end=start + len(body), marker=marker, index=len(clauses)))
    return clauses
