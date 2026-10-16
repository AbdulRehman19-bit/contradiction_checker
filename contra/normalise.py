"""Normalisation. Evidence offsets refer to the *normalised* text (NFKC, collapsed whitespace,
ASCII quotes); contraction expansion is applied only to a separate matching form."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_WORD = re.compile(r"[A-Za-z']+")


@dataclass
class Normalised:
    original: str
    text: str                # offsets for evidence refer to this
    is_empty: bool
    low_conf_lang: bool = False


def clean(value, cfg: dict) -> str:
    """NFKC, ASCII-fy quotes/dashes, collapse whitespace. None/NaN -> ''."""
    if value is None or (isinstance(value, float) and value != value):
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    for src, dst in cfg["normalise"].get("char_map", {}).items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text).strip()


def expand_contractions(text: str, cfg: dict) -> str:
    """Lower-cased matching form with contractions expanded. Not offset-preserving."""
    t = text.lower()
    for src, dst in cfg["normalise"].get("irregular_contractions", {}).items():
        t = re.sub(rf"\b{re.escape(src)}", dst, t)
    t = re.sub(r"n't\b", " not", t)
    t = re.sub(r"'re\b", " are", t)
    t = re.sub(r"'ve\b", " have", t)
    t = re.sub(r"'ll\b", " will", t)
    t = re.sub(r"'d\b", " would", t)
    t = re.sub(r"'m\b", " am", t)
    t = re.sub(r"'s\b", " is", t)
    return re.sub(r"\s+", " ", t).strip()


def is_low_conf_lang(text: str, cfg: dict) -> bool:
    n = cfg["normalise"]
    words = [w.lower() for w in _WORD.findall(text)]
    if len(words) < n.get("lang_min_words", 4):
        return False
    stop = set(n.get("stopwords", []))
    return sum(w in stop for w in words) / len(words) < n.get("lang_min_stop_ratio", 0.08)


def normalise(value, cfg: dict) -> Normalised:
    text = clean(value, cfg)
    return Normalised(original="" if value is None else str(value), text=text,
                      is_empty=not text, low_conf_lang=is_low_conf_lang(text, cfg))
