"""Comparison mechanics on small texts. These tests do not measure comparison quality."""
from collections import Counter
import json

import pytest

from nemotron_challenge import compare, facts


@pytest.mark.parametrize("printed,expected", [
    ("fuch", "such"), ("fituated", "situated"), ("firft", "first"), ("himfelf", "himself"), ("fea", "sea"),
    ("fame", "fame"), ("of", "of"), ("half", "half"), ("chief", "chief"), ("fhew", "shew"), ("coffee", "coffee"),
])
def test_long_s_folds_only_when_the_s_form_is_far_more_common(printed, expected):
    assert compare.fold_long_s(printed) == expected


def test_normalisation_records_every_change():
    tokens, changes = compare.normalise("**It is fituated** on the fea; they fhew the publick road.")
    assert tokens == ["it", "is", "situated", "on", "the", "sea", "they", "show", "the", "public", "road"]
    assert changes[("fhew", "shew", "long_s")] == 1 and changes[("shew", "show", "historical_spelling")] == 1
    assert changes[("publick", "public", "historical_spelling")] == 1


def test_distinctive_words_point_to_the_corpus_that_uses_them_more():
    left = Counter({"thereof": 40, "king": 30, "the": 300})
    right = Counter({"thereof": 1, "king": 30, "the": 300, "population": 40})
    words = compare.distinctive_words(left, right)
    assert words["left"][0]["word"] == "thereof" and words["right"][0]["word"] == "population"
    assert words["left"][0]["z"] > 0 > words["right"][0]["z"]


def test_pair_overlap_is_compared_with_unrelated_articles():
    entry = "sword blade hilt weapon steel".split()
    stats = compare.pair_stats(entry, "the sword has a blade and a hilt".split(), ["the river flows to the sea".split()])
    assert stats["entry_coverage"] == 0.6 and stats["baseline_coverage"] == 0.0 and stats["lift"] is None
    assert stats["shared_words"] == ["blade", "hilt", "sword"]


def test_chunks_respect_the_size_limit():
    text = ". ".join(f"Sentence number {i} is here" for i in range(400)) + "."
    pieces = compare.chunks(text, 500)
    assert all(len(piece) <= 500 for piece in pieces) and " ".join(pieces).count("Sentence") == 400


def test_quotes_are_checked_after_normalisation():
    source = "SYDENHAM (Dr Thomas), an excellent English phyfician, was the fon of William Sydenham"
    assert facts.quote_found("an excellent English physician", source)
    assert not facts.quote_found("a famous English surgeon", source)
    assert not facts.quote_found(None, source)


def test_claims_reply_is_validated():
    content = json.dumps({"claims": [
        {"claim": "Born 1624", "britannica_quote": "born in 1624", "verdict": "agrees", "wikipedia_quote": "1624", "passage": "2"},
        {"claim": "bad verdict", "verdict": "maybe"}]})
    claims = facts.read_claims(content)
    assert len(claims) == 1 and claims[0]["passage"] == 2 and facts.read_claims("nope") is None


def test_fact_pairs_prefer_the_subtopic_article():
    entries = {"p:e1": {"text": "x" * 200}, "p:e2": {"text": "short"}}
    results = [{"entry_id": "p:e1", "target": "topic", "decision": "accepted", "page_id": "1"},
               {"entry_id": "p:e1", "target": "subtopic", "decision": "accepted", "page_id": "2"},
               {"entry_id": "p:e2", "target": "topic", "decision": "accepted", "page_id": "3"}]
    assert [row["page_id"] for row in facts.fact_pairs({"results": results}, entries)] == ["2"]


def test_c_tf_idf_labels_each_topic_with_its_own_words():
    labels = compare.c_tf_idf({0: "sword blade sword hilt steel", 1: "river water river flood bank"}, top=2)
    assert set(labels[0]) <= {"sword", "blade", "hilt", "steel", "sword blade", "blade sword", "sword hilt", "hilt steel"}
    assert labels[1][0] == "river"


def test_long_s_misreads_that_are_words_change_only_in_checked_contexts():
    tokens, changes = compare.normalise("In the fame manner the fun is laid to fet. The keel is laid flat.")
    assert tokens == ["in", "the", "same", "manner", "the", "sun", "is", "said", "to", "set", "the", "keel", "is", "laid", "flat"]
    assert changes[("fame", "same", "long_s_context")] == 1 and changes[("laid", "said", "long_s_context")] == 1
    assert compare.normalise("the fame of the band", historical=False)[0][1] == "fame"
