"""Generic word-level resources: sentiment polarity (VADER lexicon + YAML extras) and WordNet/YAML antonyms.
These are static dictionaries, not models. Both degrade gracefully when NLTK data is missing."""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _vader() -> dict:
    try:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        return dict(SentimentIntensityAnalyzer().lexicon)
    except Exception:  # noqa: BLE001 - lexicon missing: run without it
        return {}


def lexicon_status() -> str | None:
    return None if _vader() else "VADER sentiment lexicon unavailable (nltk 'vader_lexicon'); using only the YAML word lists"


def polarity_table(cfg: dict) -> dict[str, float]:
    """word -> signed weight in (0, 1]. YAML extras win over VADER."""
    sl = cfg["markers"].get("sentiment_lexicon", {})
    skip = {str(w).lower() for w in sl.get("skip", [])}
    table: dict[str, float] = {}
    if sl.get("use_vader", True):
        thr = sl.get("vader_min_abs", 1.5)
        for w, v in _vader().items():
            if abs(v) >= thr and w.isalpha() and w not in skip:
                table[w] = 0.7 if v > 0 else -0.7
    for w in sl.get("extra_positive", []):
        table[w.lower()] = 0.75
    for w in sl.get("extra_negative", []):
        table[w.lower()] = -0.75
    return table


@lru_cache(maxsize=4096)
def _wn_antonyms(word: str) -> frozenset:
    try:
        from nltk.corpus import wordnet as wn
        out = set()
        for syn in wn.synsets(word):
            for lem in syn.lemmas():
                out |= {a.name().lower() for a in lem.antonyms()}
        return frozenset(out)
    except Exception:  # noqa: BLE001
        return frozenset()


def are_antonyms(a: str, b: str, cfg: dict) -> bool:
    a, b = a.lower(), b.lower()
    if a == b:
        return False
    for x, y in cfg.get("antonyms", {}).get("pairs", []) or []:
        if {a, b} == {x.lower(), y.lower()}:
            return True
    return b in _wn_antonyms(a) or a in _wn_antonyms(b)


def poltable(cfg: dict) -> dict[str, float]:
    """Cached polarity_table (stored on the config object for the duration of a run)."""
    if "_poltable" not in cfg:
        cfg["_poltable"] = polarity_table(cfg)
    return cfg["_poltable"]
