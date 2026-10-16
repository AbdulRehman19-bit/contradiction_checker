import pytest

from contra.nonefilter import CONTENT, HEDGED_NONE, NODATA, NONE, detect_none


@pytest.mark.parametrize("text,kind", [
    ("Nothing", NONE),
    ("nothing.", NONE),
    ("None", NONE),
    ("Nope", NONE),
    ("No complaints", NONE),
    ("Nothing displeases me", NONE),
    ("I have nothing to complain about", NONE),
    ("I can't think of anything", NONE),
    ("Nothing at all", NONE),
    ("Not really", NONE),
    ("Honestly, nothing", NONE),
    ("Nothing, it's very good.", NONE),
    ("Honestly, I have nothing against this product. It's crunchy and I particularly like the taste.", NONE),
    ("Nothing, just needs a little more white chocolate in the filling.", HEDGED_NONE),
    ("Nothing is perfect", HEDGED_NONE),
    ("None, but it could be less sweet", HEDGED_NONE),
    ("Too sweet on the palate", CONTENT),
    ("The sweetness could be toned down slightly", CONTENT),
    ("Taste", CONTENT),
    ("n/a", NODATA),
    ("N/A", NODATA),
    ("", NODATA),
    (None, NODATA),
    (float("nan"), NODATA),
    ("   ", NODATA),
])
def test_kind(cfg, text, kind):
    assert detect_none(text, cfg).kind == kind


def test_none_with_praise_flag(cfg):
    r = detect_none("Nothing, it's very good.", cfg)
    assert r.kind == NONE and r.has_praise


def test_praise_after_nothing_against(cfg):
    r = detect_none("Honestly, I have nothing against this product. It's crunchy and I particularly like the taste.", cfg)
    assert r.has_praise


def test_pure_none_no_praise(cfg):
    assert not detect_none("Nothing", cfg).has_praise


def test_hedge_reasons(cfg):
    assert detect_none("Nothing is perfect", cfg).hedge_reason == "hedge_phrase"
    assert detect_none("Nothing, just needs more filling", cfg).hedge_reason == "complaint_after_none"


def test_other_domain(cfg):
    assert detect_none("No issues with the battery", cfg).kind == NONE
    assert detect_none("Nothing, but the battery drains fast", cfg).kind == HEDGED_NONE
    assert detect_none("The checkout flow is slow", cfg).kind == CONTENT
