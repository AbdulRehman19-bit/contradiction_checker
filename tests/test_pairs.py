"""Spec fixtures (from the sample data) + a different-domain set to prove nothing is cereal specific."""
import pytest

from contra import analyze_pair


def label(cfg, like, dislike):
    return analyze_pair(like, dislike, {"cfg": cfg})


@pytest.mark.parametrize("like,dislike,expected", [
    ("I love the speculoos flavor!", "Nothing", "NO_COMPLAINT"),
    ("Good taste", "Nothing, just needs a little more white chocolate in the filling.", "SELF_CONFLICT"),
    ("Good taste", "Nothing, it's very good.", "NO_COMPLAINT"),
    ("Good taste", "Nothing is perfect", "SELF_CONFLICT"),
    ("Good taste", "Honestly, I have nothing against this product. It's crunchy and I particularly like the taste.", "MISPLACED_POSITIVE"),
    ("Good taste", "Nothing to complain about, I'll buy this product again. Very satisfied.", "MISPLACED_POSITIVE"),
    ("Good taste", "I loved it", "MISPLACED_POSITIVE"),
    ("Everything about this product is well done. A little sweet, I think, but oh well.", "Too long to wait", "MISPLACED_NEGATIVE"),
    ("The taste", "Sugar", "TENSION"),
    ("The taste", "The taste", "CONTRADICTION"),
    ("The simple, not-too-sweet taste", "All I can think of is the overly sweet taste", "CONTRADICTION"),
    ("Speculoos flavour paired with a satisfying crunch", "It is just a little bit too sweet", "CONSISTENT"),
    ("It has a good speculoos flavor", "White chocolate notes are too subtle", "CONSISTENT"),
    ("Good taste", "There was nothing I disliked, and the cereal delivered an enjoyable experience.", "MISPLACED_POSITIVE"),
    ("Good taste", "I did not find any aspect of the cereal disappointing.", "NO_COMPLAINT"),
    ("I like the taste", "I don't like the taste", "CONTRADICTION"),
    ("The taste is great", "The taste is awful", "CONTRADICTION"),
    ("The white chocolate is clearly noticeable", "The white chocolate is barely detectable", "CONTRADICTION"),
    ("White chocolate brings a smooth, sweet note that makes the overall flavour enjoyable.",
     "The excessive sugary taste takes away from the overall enjoyment.", "TENSION"),
    ("I love the crispness, the melt-in-your-mouth chocolate inside, and the taste of speculoos",
     "There isn't enough filling to balance the flavors.", "TENSION"),
    ("The creamy white chocolate flavour stands out", "The taste of speculoos", "CONSISTENT"),
    ("Tasty", None, "NO_DATA"),
    (None, "Too sweet", "NO_DATA"),
])
def test_label(cfg, like, dislike, expected):
    assert label(cfg, like, dislike).label == expected


def test_same_direction_not_contradiction(cfg):
    assert label(cfg, "A little sweet but fine", "Too sweet").label != "CONTRADICTION"


@pytest.mark.parametrize("like,dislike,expected", [
    ("The battery life is great", "The battery life is terrible", "CONTRADICTION"),
    ("Friendly staff", "Nothing", "NO_COMPLAINT"),
    ("Great service at the hotel", "The service was not good", "CONTRADICTION"),
    ("I like the app design", "The app design is not to my liking", "CONTRADICTION"),
    ("Fast delivery", "The screen is too small", "CONSISTENT"),
    ("Good battery", "Nothing, but the charger is slow", "SELF_CONFLICT"),
])
def test_other_domains(cfg, like, dislike, expected):
    assert label(cfg, like, dislike).label == expected


def test_result_has_evidence_and_rule(cfg):
    r = label(cfg, "I like the taste", "I don't like the taste")
    assert r.like_evidence and r.dislike_evidence and r.rule_ids and r.explanation
    assert r.aspect == "taste"


def test_bare_conflict_is_contradiction_with_flag(cfg):
    r = label(cfg, "The taste and texture", "The taste")
    assert r.label == "CONTRADICTION" and "BARE_ASPECT_CONFLICT" in r.extra_flags


@pytest.mark.parametrize("like,dislike,expected", [
    ("Fast", "Slow to load", "CONTRADICTION"),
    ("Arrived early", "Arrived late", "CONTRADICTION"),
    ("Quiet room", "Noisy at night", "CONTRADICTION"),
    ("I like it", "I do not like it", "CONTRADICTION"),
    ("Intuitive", "Intuitive", "CONTRADICTION"),
    ("The flavour combination works really well", "The flavour combination does not work for me", "CONTRADICTION"),
    ("Very crunchy", "Not crunchy enough", "CONTRADICTION"),
    ("Great value", "Overpriced", "CONTRADICTION"),
    ("The filling is generous", "Not enough filling", "TENSION"),
    ("Clear explanations", "Some explanations were unclear", "TENSION"),
    ("Everything is great except the battery", "Battery life", "MISPLACED_NEGATIVE"),
    ("Rich taste", "Nothing wrong with the taste, but the box was crushed on arrival", "CONSISTENT"),
    ("Excellent", "Rien", "NO_COMPLAINT"),
    ("Smooth and responsive", "Nothing, it works perfectly", "MISPLACED_POSITIVE"),
    ("Tasty", "asdf", "NO_DATA"),
])
def test_new_domain_cases(cfg, like, dislike, expected):
    assert label(cfg, like, dislike).label == expected
