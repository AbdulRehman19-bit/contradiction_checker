import pandas as pd
import pytest

from contra.io import ColumnDetectionError, detect_columns
from contra.normalise import expand_contractions, normalise
from contra.segment import split_clauses


def test_expand(cfg):
    assert expand_contractions("It doesn't taste good, can't say", cfg) == "it does not taste good, can not say"
    assert expand_contractions("I'm sure it isn't", cfg) == "i am sure it is not"


def test_clean(cfg):
    n = normalise("  The’s   taste \n", cfg)
    assert n.text == "The's taste" and not n.is_empty
    assert normalise(None, cfg).is_empty and normalise(float("nan"), cfg).is_empty


def test_low_conf_lang(cfg):
    assert normalise("Le gout est vraiment tres bon pour moi", cfg).low_conf_lang
    assert not normalise("The taste is really good for me", cfg).low_conf_lang


def test_segments_with_offsets(cfg):
    text = "A little sweet, I think, but oh well."
    cl = split_clauses(text, cfg)
    assert [c.text for c in cl] == ["A little sweet", "I think", "oh well."]
    assert cl[2].marker == "but"
    for c in cl:
        assert text[c.start:c.end] == c.text


def test_contrast_marker_attached(cfg):
    cl = split_clauses("Crunchy but too hard", cfg)
    assert [c.text for c in cl] == ["Crunchy", "too hard"]
    assert cl[1].marker == "but"


def test_hedged_none_split(cfg):
    assert [c.text for c in split_clauses("Nothing, just needs more filling.", cfg)] == ["Nothing", "just needs more filling."]


def test_empty(cfg):
    assert split_clauses("", cfg) == []


def test_detect_columns():
    df = pd.DataFrame(columns=["What did you LIKE about this product? - value", "What did you DISLIKE about this product? - value"])
    assert detect_columns(df) == tuple(df.columns)
    with pytest.raises(ColumnDetectionError):
        detect_columns(pd.DataFrame(columns=["a", "b"]))


def test_read_keeps_na_and_none_text(tmp_path):
    from contra.io import read_table
    f = tmp_path / "a.csv"
    f.write_text("LIKE,DISLIKE\ngood,N/A\ngreat,None\nnice,\nok,NA\n", encoding="utf-8")
    df = read_table(f)
    assert list(df["DISLIKE"]) == ["N/A", "None", "", "NA"]
