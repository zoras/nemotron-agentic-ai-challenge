"""Site and LaTeX helpers. These tests do not compile documents."""
from nemotron_challenge import site


def test_tex_escape_handles_specials_and_markdown_emphasis():
    assert site.tex_escape("**SWORD**, 50% of _the_ cost & more $5 #1") == (
        r"\textbf{SWORD}, 50\% of \textit{the} cost  |  more \$5 \#1")
    assert site.tex_escape("a\\b {c}") == r"a\textbackslash{}b \{c\}"


def test_page_tex_has_source_and_record_sections():
    record = {"filename": "page-0001-abc.jpg", "page_id": "p", "row_index": 1, "volume_id": "v", "image_sha256": "f" * 64,
              "status": "blank", "status_evidence": {"ink_fraction": 0.001}, "running_head": "", "regions": [], "blocks": []}
    summary = {"dataset": "d", "dataset_revision": "r", "parse_model": "m", "code_revision": "c"}
    tex = site.page_tex(record, [], summary, "Latin Modern Roman")
    assert tex.index(r"\section*{Historical source}") < tex.index(r"\section*{Source record}")
    assert "classified as \\textit{blank}" in tex and tex.rstrip().endswith(r"\end{document}")


def test_html_pages_keep_navigation_and_escape_text():
    page = site.page_html("A <b> title", "<p>body</p>", depth=1)
    assert "A &lt;b&gt; title" in page and 'href="../analysis.html"' in page


def test_how_page_shows_architecture_example_entry_and_its_match(tmp_path):
    from nemotron_challenge import site_how

    entry_id = site_how.EXAMPLE_ENTRY
    entry = {"title": "SYDENHAM", "kind": "headword", "text": "SYDENHAM (Dr Thomas), an excellent English phyfician.",
             "source": [{"bbox": [0.5, 0.6, 0.9, 0.9]}],
             "match": {"topic": {"title": "Thomas Sydenham", "decision": "accepted"}}}
    index = {"entries": {entry_id: entry}, "corpus": {"fact_counts": {"claims": 4, "verdicts": {"agrees": 4}}}}
    ranked = [{"title": "Thomas Sydenham", "embed_rank": 1, "cosine": 0.488, "rerank_logit": 0.88, "navigation": False},
              {"title": "Sydenham", "embed_rank": 54, "cosine": 0.111, "rerank_logit": -1.05, "navigation": True}]
    matches = {"counts": {"decisions": {"topic": {"accepted": 1}}},
               "plans": {entry_id: {"topic": "Thomas Sydenham", "topic_description": "An English physician."}},
               "results": [{"entry_id": entry_id, "target": "topic", "label": "Thomas Sydenham", "decision": "accepted",
                            "title": "Thomas Sydenham", "reason": "logit 0.88", "candidates": 55,
                            "titles": ["Thomas Sydenham"], "searches": ["thomas sydenham english physician 1624"],
                            "ranked": ranked}]}
    body = site_how.how_body(index, matches, {"counts": {"pairs": 1, "long_s_changes": 3628}}, tmp_path, tmp_path)
    assert "<svg" in body and "Our Nebius GPU endpoint" in body
    assert "e1</span><b>SYDENHAM</b>" in body and "page-entries.jpg" not in body  # no scan, so no figure
    assert "<b>55</b> different candidate articles" in body and "(disambiguation, not eligible)" in body
    assert "3,628 recorded long-s fixes" in body
