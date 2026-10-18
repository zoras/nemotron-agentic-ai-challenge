"""Match mechanics with fake services. These tests do not measure match quality."""
import json

import pytest

from nemotron_challenge import match
from nemotron_challenge.config import EMBED_DIMENSIONS


def test_plain_text_drops_markup_and_joins_line_end_hyphens():
    assert match.plain("**SWORD**, an offen-\nfive _weapon_ \\\\ & more") == "SWORD, an offenfive weapon more"


@pytest.mark.parametrize("title,lead,expected", [
    ("Sword (disambiguation)", "", True), ("Lists of swords", "", True),
    ("Abyssinia", "Abyssinia may refer to: the Ethiopian Empire", True), ("Sword", "A sword is a bladed weapon", False),
    ("Britain", "Britain most often refers to:\n\nGreat Britain, a large island", True),
    ("Escalade", "Escalade is the act of scaling defensive walls", False),
    ("Oratory", "Oratory is a type of public speaking.\n\nOratory may also refer to:", True),
    ("Amida", "Amida can mean :  Amida (Mesopotamia), now Diyarbakir", True),
    ("Ship's wheel", "it forms part of the helm (the term helm can mean the wheel alone)", False),
    ("Monarchy of the United Kingdom", "The term may also refer to the role of the royal family", False),
])
def test_navigation_pages_are_recognised(title, lead, expected):
    assert match.is_navigation(title, lead) is expected


def test_plan_reply_is_validated_per_entry():
    content = "```json\n" + json.dumps({"page_head": "SWI SYD", "entries": [
        {"entry_id": "e1", "key": "SWORD", "topic": "Sword", "wikipedia_titles": ["Sword", 5, "x" * 200],
         "queries": ["Swiss cantons", "a", "b"], "subtopic": " "},
        {"entry_id": "e9", "key": "SWORD", "topic": "not in this call"},
        {"entry_id": "e2", "key": "SYDENHAM", "topic": None},
        {"entry_id": "e3", "key": "SWITZERLAND", "topic": "Switzerland"}]}) + "\n```"
    plans, rejected = match.read_plan(content, {"e1": "SWORD", "e2": "SYDENHAM", "e3": "SYCOPHANT"})
    assert list(plans) == ["e1"] and list(rejected) == ["e3"]
    assert plans["e1"]["wikipedia_titles"] == ["Sword"] and plans["e1"]["queries"] == ["Swiss cantons", "a"]
    assert plans["e1"]["subtopic"] is None and plans["e1"]["page_head"] == "SWI SYD"
    assert match.read_plan("not json", {"e1": "SWORD"}) == ({}, {})


@pytest.mark.parametrize("reply,expected,same", [
    ("SWORD", "SWORD", True), ("sword.", "SWORD ", True), ("HELSTON", "HELSINGIA", False), (None, "SWORD", False),
    ("THORACIC DUCT", "THORACIC DUCT", True), ("Switzerland", "SYDENHAM", False)])
def test_plan_key_must_copy_the_entry_key(reply, expected, same):
    assert match.same_key(reply, expected) is same


class FakeHttp:
    def __init__(self, reply):
        self.reply, self.calls = reply, 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls += 1
        reply = self.reply

        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return reply
        return Response()


def test_titles_resolve_through_redirects_and_missing_titles_map_to_none(tmp_path):
    http = FakeHttp({"query": {"redirects": [{"from": "Fainting", "to": "Syncope (medicine)"}],
                               "pages": [{"pageid": 20254750, "title": "Syncope (medicine)"},
                                         {"title": "No such page", "missing": True}]}})
    cache = match.ReplyCache(tmp_path)
    resolved = match.resolve_titles(http, cache, ["Fainting", "No such page"])
    assert resolved == {"Fainting": {"page_id": "20254750", "live_title": "Syncope (medicine)", "redirected": True},
                        "No such page": None}
    match.resolve_titles(http, cache, ["No such page", "Fainting"])
    assert http.calls == 1 and cache.sent["title_lookup"] == 1


def lead(page_id, title, text="lead text"):
    return {"page_id": page_id, "revision_id": "1", "title": title, "url": f"u/{title}", "text_sha256": "0" * 64,
            "total_chars": 100, "lead": text}


def hit(page_id, title, rank, excerpt="excerpt"):
    return {**lead(page_id, title), "rank": rank, "bm25": 1.0, "excerpt_offset": 0, "excerpt": excerpt}


def test_candidates_merge_title_lookups_and_keyword_hits():
    target = {"titles": ["Sword"], "searches": ["sword weapon"]}
    rows = match.gather_candidates(
        target, {"Sword": {"page_id": "1", "live_title": "Sword", "redirected": False}}, {"1": lead("1", "Sword")},
        {"sword weapon": [hit("1", "Sword", 3), hit("2", "Sword (disambiguation)", 1)]})
    by_id = {row["page_id"]: row for row in rows}
    assert by_id["1"]["sources"] == ["title:Sword", "bm25:3:sword weapon"] and not by_id["1"]["navigation"]
    assert by_id["2"]["navigation"] and by_id["1"]["document"] == "Sword\n\nlead text"


def ranked(*rows):
    return [{"page_id": str(i), "title": title, "navigation": nav, "sources": sources, "rerank_logit": logit,
             "embed_rank": i + 1} for i, (title, nav, sources, logit) in enumerate(rows)]


def test_decision_skips_navigation_and_uses_the_thresholds_of_its_group():
    headword = ("topic", "headword")
    result = match.decide(ranked(("Sword (disambiguation)", True, ["bm25:1:q"], 9.0),
                                 ("Sword", False, ["title:Sword"], -3.4), ("Katana", False, ["bm25:2:q"], -5.0)), headword)
    assert (result["decision"], result["title"], result["margin"]) == ("accepted", "Sword", 1.6)
    keyword = match.decide(ranked(("Katana", False, ["bm25:2:q"], -3.4)), headword)
    assert keyword["decision"] == "uncertain" and "keyword search" in keyword["reason"]
    # A continuation topic is queried with a modern description, so the same logit is not enough there.
    assert match.decide(ranked(("Sword", False, ["title:Sword"], -4.5)), ("topic", "continuation"))["decision"] == "uncertain"
    assert match.decide(ranked(("Katana", False, ["bm25:2:q"], -6.0)), headword)["decision"] == "no_match"
    assert match.decide(ranked(("Lists of swords", True, [], 5.0)), headword)["decision"] == "no_match"


class FakeRetrieval:
    def __init__(self):
        self.embed_calls, self.rerank_calls = 0, 0

    def embed(self, texts, input_type):
        self.embed_calls += 1
        return [[1.0] + [0.0] * (EMBED_DIMENSIONS - 1) if "sword" in text.lower()
                else [0.0, 1.0] + [0.0] * (EMBED_DIMENSIONS - 2) for text in texts]

    def rerank(self, query, documents):
        self.rerank_calls += 1
        scores = [3.0 if document.startswith("Sword") else -1.0 for document in documents]
        return sorted([{"index": i, "relevance_score": s} for i, s in enumerate(scores)], key=lambda r: -r["relevance_score"])


def test_vectors_are_cached_in_lancedb_and_reranking_is_cached(tmp_path):
    retrieval = FakeRetrieval()
    vectors = match.VectorCache(tmp_path / "db")
    docs = ["Sword\n\nA sword", "Katana\n\nA katana"]
    first = vectors.embed(retrieval, docs, "document")
    again = match.VectorCache(tmp_path / "db").embed(retrieval, docs, "document")
    assert retrieval.embed_calls == 1 and [list(map(round, v[:2])) for v in again] == [[1, 0], [0, 1]]
    assert first[0][0] == 1.0
    candidates = [{"document": doc, "sources": ["bm25:1:q"]} for doc in docs]
    target = {"query": "SWORD, an offensive weapon"}
    cache = match.ReplyCache(tmp_path / "raw")
    query_vector = vectors.embed(retrieval, [target["query"]], "query")[0]
    order = match.rank_target(target, candidates, query_vector, dict(zip(docs, first)), retrieval, cache)
    assert [row["document"][:5] for row in order] == ["Sword", "Katan"] and order[0]["embed_rank"] == 1
    match.rank_target(target, candidates, query_vector, dict(zip(docs, first)), retrieval, cache)
    assert retrieval.rerank_calls == 1


def test_targets_add_a_subtopic_for_continuations():
    entries = [{"entry_id": "p:e1", "kind": "continuation", "title": "INDIA", "text": "Palibothra was a city."},
               {"entry_id": "p:e2", "kind": "headword", "title": "SWORD", "text": "SWORD, an offensive weapon."}]
    plans = {"p:e1": {"topic": "India", "topic_description": "A country in South Asia.", "wikipedia_titles": ["India"],
                      "queries": [], "subtopic": "Pataliputra", "subtopic_titles": ["Pataliputra"]}}
    targets = match.build_targets(entries, plans)
    assert [t["entry_kind"] for t in targets] == ["continuation", "continuation", "headword"]
    assert [(t["target_id"], t["label"]) for t in targets] == [
        ("p:e1#topic", "India"), ("p:e1#subtopic", "Pataliputra"), ("p:e2#topic", "Sword")]
    assert targets[0]["query"] == "India. A country in South Asia." and targets[0]["titles"] == ["India"]
    assert targets[1]["query"].startswith("Pataliputra. Palibothra") and targets[2]["titles"] == ["Sword"]


def test_busy_service_is_retried_and_a_rejected_request_is_not(monkeypatch):
    from nemotron_challenge.clients import ServiceError

    monkeypatch.setattr(match.time, "sleep", lambda seconds: None)
    replies = [ServiceError("busy", status_code=429, retry_after="1"), ServiceError("busy", status_code=503), "ok"]

    def call():
        item = replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    assert match.retrying(call) == "ok" and not replies
    with pytest.raises(ServiceError):
        match.retrying(lambda: (_ for _ in ()).throw(ServiceError("bad", status_code=422)))


class FakeChat:
    """Plans the first entry of each call, and answers the second with the first entry's key."""
    def __init__(self):
        self.calls = []

    def complete(self, messages, max_tokens=None, extra_body=None):
        content = messages[1]["content"]
        text = content[0]["text"] if isinstance(content, list) else content
        items = json.loads(text.split("Entries:\n", 1)[1])
        self.calls.append(([item["entry_id"] for item in items], isinstance(content, list)))
        first = items[0]
        reply = [{"entry_id": first["entry_id"], "key": first["key"], "topic": first["ocr_title"] or "Continued"}]
        if len(items) > 1:
            reply.append({"entry_id": items[1]["entry_id"], "key": first["key"], "topic": "drifted"})
        content = json.dumps({"page_head": "A", "entries": reply})
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}], "usage": {"completion_tokens": 9}}


def test_headwords_are_planned_from_text_and_wrong_keys_are_replanned_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(match, "head_strip", lambda path: "data:image/png;base64,AA")
    entries = [{"entry_id": "p:e1", "kind": "continuation", "title": None, "heading": None, "margin_notes": [],
                "text": "the end of an article"}]
    entries += [{"entry_id": f"p:e{n}", "kind": "headword", "title": f"T{n}", "heading": None, "margin_notes": [],
                 "text": f"T{n}, a word."} for n in range(2, 12)]
    chat = FakeChat()
    plans = match.plan_pages(chat, match.ReplyCache(tmp_path), {"p.jpg": {"page_type": "dictionary"}},
                             {"p.jpg": entries}, tmp_path, workers=1)
    assert chat.calls[:3] == [(["e1"], True), ([f"e{n}" for n in range(1, 9)], False), (["e1", "e2"], False)]
    assert len(chat.calls) == 3 + 8 and all(call == (["e1"], False) for call in chat.calls[3:])
    assert [plans[f"p:e{n}"]["topic"] for n in range(2, 12)] == [f"T{n}" for n in range(2, 12)]
    assert plans["p:e3"]["batch_error"].startswith("key 'T2'") and "batch_error" not in plans["p:e10"]
    assert plans["p:e1"]["topic"] == "Continued" and plans["p:e1"]["call"].endswith("image")
