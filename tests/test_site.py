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
