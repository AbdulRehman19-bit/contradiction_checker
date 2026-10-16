"""Aspect extraction from a clause via the spaCy dependency parse (graceful regex fallback)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_NLP = None
_NLP_ERR: str | None = None


def get_nlp():
    """Load spaCy once. Returns None (and remembers why) if the model is unavailable."""
    global _NLP, _NLP_ERR
    if _NLP is None and _NLP_ERR is None:
        try:
            import spacy
            _NLP = spacy.load("en_core_web_sm", disable=["ner"])
        except Exception as exc:  # noqa: BLE001 - degrade, never crash
            _NLP_ERR = f"spaCy model en_core_web_sm unavailable ({exc}); using regex fallback for aspects"
    return _NLP


def nlp_status() -> str | None:
    get_nlp()
    return _NLP_ERR


@dataclass(frozen=True)
class Aspect:
    head: str                      # canonical head noun
    nouns: frozenset               # canonical head + noun modifiers
    phrase: str                    # surface phrase
    bare: bool = False             # clause is nothing but this noun phrase


@dataclass
class ParsedClause:
    aspects: list[Aspect] = field(default_factory=list)
    has_verb: bool = False
    adjectives: list[str] = field(default_factory=list)


def canon(word: str, cfg: dict) -> str:
    """Canonical aspect key: lower-case, alias map, light 'ness' stripping, adjective->attribute map."""
    a = cfg["aspects"]
    w = word.lower().strip()
    w = a.get("aliases", {}).get(w, w)
    w = a.get("adjective_attributes", {}).get(w, w)
    if w.endswith("ness") and len(w) > 6:
        base = w[:-4]
        w = a.get("adjective_attributes", {}).get(base, w)
    return a.get("aliases", {}).get(w, w)


def _generic(word: str, cfg: dict, extra: frozenset) -> bool:
    return word.lower() in {g.lower() for g in cfg["aspects"]["generic_nouns"]} or word.lower() in extra


def parse_clause(text: str, cfg: dict, extra_generic: frozenset = frozenset()) -> ParsedClause:
    nlp = get_nlp()
    return _parse_spacy(nlp(text), cfg, extra_generic) if nlp else _parse_fallback(text, cfg, extra_generic)


def _parse_spacy(doc, cfg: dict, extra: frozenset) -> ParsedClause:
    attrs = cfg["aspects"]["adjective_attributes"]
    out = ParsedClause()
    out.has_verb = any(t.pos_ in {"VERB", "AUX"} for t in doc)
    consumed: set[int] = set()
    for chunk in doc.noun_chunks:
        if chunk.start in consumed:
            continue
        root = chunk.root
        if root.pos_ == "PRON" or _generic(root.lemma_, cfg, extra):
            continue
        toks = [t for t in chunk if t.pos_ in {"NOUN", "PROPN"} and not _generic(t.lemma_, cfg, extra)]
        # "the taste of speculoos": fold the 'of' complement into the same aspect
        for child in root.children:
            if child.dep_ == "prep" and child.lemma_ == "of":
                for pobj in child.children:
                    if pobj.dep_ == "pobj":
                        consumed.add(pobj.left_edge.i)
                        toks += [t for t in pobj.subtree if t.pos_ in {"NOUN", "PROPN"} and not _generic(t.lemma_, cfg, extra)]
        if not toks:
            continue
        head = canon(root.lemma_, cfg)
        nouns = frozenset(canon(t.lemma_, cfg) for t in toks) | {head}
        out.aspects.append(Aspect(head=head, nouns=nouns, phrase=chunk.text))
        for t in chunk:  # adjective modifiers that map to an attribute ("sweet note" -> sweetness)
            if t.pos_ == "ADJ" and t.lemma_.lower() in attrs:
                a = canon(t.lemma_, cfg)
                out.aspects.append(Aspect(head=a, nouns=frozenset({a}), phrase=t.text))
    for t in doc:
        if t.pos_ == "ADJ":
            out.adjectives.append(t.lemma_.lower())
    # adjective-only clause ("too sweet"): the adjective names the aspect via the attribute map
    if not out.aspects:
        for lemma in out.adjectives:
            a = canon(lemma, cfg)
            if not _generic(a, cfg, extra) and lemma in attrs:
                out.aspects.append(Aspect(head=a, nouns=frozenset({a}), phrase=lemma))
    # also catch attribute adjectives sitting outside any noun chunk ("too sweet on the palate")
    have = {a.head for a in out.aspects}
    for lemma in out.adjectives:
        if lemma in attrs and canon(lemma, cfg) not in have:
            a = canon(lemma, cfg)
            out.aspects.append(Aspect(head=a, nouns=frozenset({a}), phrase=lemma))
            have.add(a)
    if len(out.aspects) == 1 and not out.has_verb and not out.adjectives:
        a = out.aspects[0]
        out.aspects[0] = Aspect(a.head, a.nouns, a.phrase, bare=True)
    return out


_STOP = set("a an the of to is it in this that i very with for on are as be its my me not no but too more was so have has and or at by from".split())


def _parse_fallback(text: str, cfg: dict, extra: frozenset) -> ParsedClause:
    words = [w for w in re.findall(r"[a-z']+", text.lower()) if w not in _STOP and not _generic(w, cfg, extra)]
    out = ParsedClause()
    for w in words:
        c = canon(w, cfg)
        out.aspects.append(Aspect(head=c, nouns=frozenset({c}), phrase=w))
    if len(text.split()) <= 3 and len(out.aspects) == 1:
        a = out.aspects[0]
        out.aspects[0] = Aspect(a.head, a.nouns, a.phrase, bare=True)
    return out


def relation(a: Aspect, b: Aspect, cfg: dict | None = None) -> str:
    """SAME / PARENT_CHILD / SIBLING / UNRELATED between two aspects."""
    if a.nouns == b.nouns:
        return "SAME"
    if a.nouns < b.nouns or b.nouns < a.nouns:
        return "PARENT_CHILD"
    for parent, children in ((cfg or {}).get("aspects", {}).get("hierarchy", {}) or {}).items():
        kids = set(children)
        if (a.head == parent and b.head in kids) or (b.head == parent and a.head in kids):
            return "PARENT_CHILD"
    if a.head == b.head or (a.nouns & b.nouns):
        return "SIBLING"
    return "UNRELATED"
