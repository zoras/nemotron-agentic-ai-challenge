"""Entry splitting and joining with synthetic page records. These tests do not measure segmentation accuracy."""
import pytest

from nemotron_challenge import entries


def record(row, head, blocks, status="text", volume="v1"):
    stem = f"page-{row:04d}-abc"
    return {
        "page_id": f"britannica:rev:train:{row}", "row_index": row, "volume_id": volume, "filename": f"{stem}.jpg",
        "image_sha256": "abc", "status": status, "running_head": head,
        "blocks": [{"id": f"{stem}:b{order}", "class": cls, "text": text, "bbox": bbox}
                   for order, (cls, text, bbox) in enumerate(blocks)],
    }


LEFT, RIGHT = [0.08, 0.2, 0.48, 0.5], [0.52, 0.2, 0.92, 0.5]


@pytest.mark.parametrize("head,page_type,guide,title", [
    ("S W I [ 248 ] S Y D", "dictionary", ["SWI", "SYD"], None),
    ("R E S [ 752 JRES", "dictionary", ["RES", "RES"], None),
    ("E S C 1723 I E S C", "dictionary", ["ESC", "ESC"], None),
    ("THOTHR 239", "dictionary", ["THO", "THR"], None),
    ("ABYSSINIA. 57", "article", [], "ABYSSINIA"),
    ("5550 O P T I C S. Part II.", "article", [], "OPTICS"),
    ("466 CONCHOLO GY. Chap. 1", "article", [], "CONCHOLOGY"),
    ("948 LAW.", "article", [], "LAW"),
    ("( 5", "unknown", [], None),
])
def test_running_head_gives_page_type(head, page_type, guide, title):
    result = entries.read_head(head, [])
    assert (result["page_type"], result["guide_words"], result["head_title"]) == (page_type, guide, title)


def test_guide_words_can_come_from_column_tops():
    blocks = [{"class": "Title", "text": "E R A", "bbox": [0.2, 0.04, 0.3, 0.06]}]
    assert entries.read_head("( 5", blocks)["guide_words"] == ["ERA"]


def test_dictionary_page_splits_at_headwords_and_keeps_sub_entries():
    page = record(251, "S W I [ 248 ] S Y D", [
        ("Page-header", "S W I [ 248 ] S Y D", [0.0, 0.0, 1.0, 0.03]),
        ("Caption", "Switzerland,", [0.02, 0.03, 0.08, 0.06]),
        ("Text", "parts of the country that border on Italy.", LEFT),
        ("Text", "SWORD, an offensive weapon worn at the fide.", RIGHT),
        ("Text", "_Sword of State,_ which is borne before the king.", RIGHT),
        ("Section-header", "OVID.", RIGHT),
        ("Text", "SWOONING. See MEDICINE, n° 274.", RIGHT),
        ("Text", "SYDENHAM (Dr Thomas), an excellent English phyfician.", RIGHT),
        ("Page-footer", "for", [0.9, 0.93, 0.92, 0.94]),
    ])
    found, segmentation = entries.page_entries(page)
    assert [(entry["kind"], entry["title"], entry["title_source"]) for entry in found] == [
        ("continuation", "Switzerland", "margin_note"), ("headword", "SWORD", "headword"),
        ("headword", "SWOONING", "headword"), ("headword", "SYDENHAM", "headword")]
    assert "Sword of State" in found[1]["text"] and "OVID." in found[1]["text"]
    assert found[2]["see"] == ["MEDICINE"] and found[3]["heading"] == "SYDENHAM (Dr Thomas)"
    assert found[0]["starts_on_earlier_page"] and found[-1]["may_continue"] and not found[1]["may_continue"]
    assert found[1]["parts"][0]["block_ids"] == ["page-0251-abc:b3", "page-0251-abc:b4", "page-0251-abc:b5"]
    assert segmentation["excluded_chars"] == {"Page-header": 19, "Caption": 12, "Page-footer": 3}


def test_early_editions_file_i_with_j():
    page = record(493, "I L A [ 159 ] I L A", [
        ("Text", "JILLIFREE, a town on the northern bank of the river Gambia.", LEFT),
        ("Text", "ILAY, or Isla, one of the Hebrides.", LEFT),
    ])
    assert [entry["title"] for entry in entries.page_entries(page)[0]] == ["JILLIFREE", "ILAY"]


def test_article_page_is_one_entry_even_with_capitalised_section_heads():
    page = record(2424, "AGRICULTURE. 345", [
        ("Text", "the flocks were driven to the hills.", LEFT),
        ("Section-header", "SHEEP.", RIGHT),
        ("Text", "SHEEP, of all animals, require the driest pasture.", RIGHT),
    ])
    found, segmentation = entries.page_entries(page)
    assert len(found) == 1 and found[0]["title"] == "AGRICULTURE" and segmentation["page_type"] == "article"


def test_continuation_title_from_a_margin_name_merged_into_the_first_line():
    page = record(318, "N I L [ 75 JNIL", [("Text", "**Nile.** or White River, which, according to the accounts", LEFT)])
    found, _ = entries.page_entries(page)
    assert (found[0]["title"], found[0]["title_source"]) == ("Nile", "merged_margin_note")


def test_consecutive_scans_join_only_on_consecutive_pages_with_agreeing_titles():
    pages = [
        record(2569, "ABYSSINIA. 57", [("Text", "her affairs entirely to Frumentius.", LEFT)]),
        record(2570, "88 ABYSSINIA.", [("Text", "dag already mentioned.", LEFT)]),
        record(10, "ABYSSINIA. 87", [("Text", "the war of the elephant.", LEFT)], volume="v3"),
        record(11, "88 ABYSSINIA.", [("Text", "dag already mentioned.", LEFT)], volume="v3"),
        record(20, "S W I [ 24 ] S W I", [("Caption", "_Swift._", [0.03, 0.04, 0.1, 0.07]), ("Text", "Swift left.", LEFT)],
               volume="v4"),
        record(21, "W I L [ 25 ] W I L", [("Text", "lorhip, and fome time after.", LEFT)], volume="v4"),
        record(1614, "T H O ( 896 ) T H O", [("Text", "THORN, a city of Poland.", LEFT)], volume="v2"),
        record(1615, "", [], status="blank", volume="v2"),
    ]
    result = entries.build_entries(pages)
    joins = {join["from"][5:9]: (join["joined"], join["reason"]) for join in result["joins"]}
    assert joins["2569"] == (False, "printed page numbers do not follow each other: 57 / 88")
    assert joins["0010"] == (True, "titles match: ABYSSINIA / ABYSSINIA")
    assert joins["0020"] == (False, "guide word WIL does not match Swift")
    assert joins["1614"] == (False, "next scan is blank")
    joined = next(entry for entry in result["entries"] if entry.get("joined_from"))
    assert [part["row_index"] for part in joined["parts"]] == [10, 11]
    assert joined["text"].endswith("dag already mentioned.") and result["counts"]["joined"] == 1
    assert result["counts"]["entries"] == 6
