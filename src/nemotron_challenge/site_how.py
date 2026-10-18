"""The "How it works" page: an architecture diagram and one page and one entry followed through the pipeline.

Numbers and examples come from the saved artifacts, so a rebuild after a new run stays correct. The example
page and entry are fixed; a section is left out when its example is not in the artifacts.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any

EXAMPLE_PAGE = "page-0251-69952e7c4a0f"
EXAMPLE_ENTRY = "page-0251-69952e7c4a0f:e8"
BOX_COLOURS = ("#0e6e6b", "#8a2d3b", "#3b5ba5", "#b3452f", "#2e7d4f", "#7850a0", "#c88214", "#1478aa")

HOW_CSS = """
.arch{overflow-x:auto;border:1px solid var(--line);border-radius:6px;background:var(--source);padding:8px}
.arch svg{display:block;min-width:760px;width:100%;height:auto}
.arch .box{fill:var(--source);stroke:var(--line);stroke-width:1.5}.arch .band{fill:var(--generated);stroke:var(--line);stroke-width:1.5}
.arch .chip{fill:var(--bg);stroke:var(--accent);stroke-width:1.5}.arch text{fill:var(--fg);font:14px system-ui,sans-serif}
.arch .t{font-weight:700;font-size:15px}.arch .m{fill:var(--muted);font-size:12.5px}.arch .lbl{fill:var(--accent);font-size:12.5px;font-weight:600}
.arch .line{stroke:var(--accent);stroke-width:1.8;fill:none}.arch .gone{stroke-dasharray:5 4}
.entrygrid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:20px;align-items:start}
@media (max-width:820px){.entrygrid{grid-template-columns:1fr}}
.entrygrid img{width:100%;height:auto;border:1px solid var(--line)}.tag{display:inline-block;min-width:2.2em;text-align:center;
color:#fff;border-radius:4px;font:700 .75rem/1.6 system-ui,sans-serif;margin-right:6px}
.defs dt{font-weight:700;margin-top:10px}.defs dd{margin:0 0 0 0}.vec{font-family:ui-monospace,Menlo,monospace;font-size:.85rem}
"""


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def architecture_svg() -> str:
    """Where each part runs and what flows between them. Colours come from the site's CSS variables."""
    chips = ["1 Extract", "2 Match", "3 Compare", "4 Agent index", "5 Site", "6 Evaluate"]
    chip_svg = "".join(
        f'<rect class="chip" x="{36 + i * 144}" y="250" width="128" height="56" rx="6"/>'
        f'<text x="{100 + i * 144}" y="283" text-anchor="middle" class="t">{name}</text>'
        + (f'<path class="line" d="M{164 + i * 144},278 h14" marker-end="url(#a)"/>' if i < 5 else "")
        for i, name in enumerate(chips))
    return f"""<svg viewBox="0 0 1000 600" role="img" aria-label="Architecture: organizer servers, our GPU endpoint and Token Factory feed the six pipeline stages; the Hermes agent reads the saved index; GitHub Pages serves the site">
<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="var(--accent)"/></marker></defs>
<rect class="box" x="20" y="20" width="300" height="120" rx="8"/>
<text x="36" y="48" class="t">Organizer servers</text><text x="36" y="74">Nemotron Parse 3.5</text>
<text x="36" y="96">Wikipedia API and BM25 search</text><text x="36" y="118" class="m">7.2 million articles, pinned snapshot</text>
<rect class="box" x="350" y="20" width="300" height="120" rx="8"/>
<text x="366" y="48" class="t">Our Nebius GPU endpoint</text><text x="366" y="74">Nemotron Embed VL 1B</text>
<text x="366" y="96">Nemotron Rerank VL 1B</text><text x="366" y="118" class="m">RTX PRO 6000, deleted after the run</text>
<rect class="box" x="680" y="20" width="300" height="120" rx="8"/>
<text x="696" y="48" class="t">Nebius Token Factory</text><text x="696" y="74">Nemotron 3.5 Super VL</text>
<text x="696" y="96">title plans, fact claims,</text><text x="696" y="118">every agent step</text>
<rect class="band" x="20" y="200" width="880" height="160" rx="8"/>
<text x="36" y="228" class="t">Our pipeline: one command per stage, run on the laptop</text>
{chip_svg}
<text x="36" y="342" class="m">Each stage saves its output in artifacts/ (in Git). Embeddings are cached in LanceDB.</text>
<path class="line" d="M100,140 V246" marker-end="url(#a)"/><text x="108" y="176" class="lbl">scans → text</text>
<path class="line" d="M244,140 V246" marker-end="url(#a)"/><text x="252" y="196" class="lbl">candidates</text>
<path class="line gone" d="M470,140 L300,246" marker-end="url(#a)"/><path class="line gone" d="M500,140 L400,246" marker-end="url(#a)"/>
<text x="512" y="166" class="lbl">vectors, scores</text>
<path class="line" d="M740,140 L320,250" marker-end="url(#a)"/><path class="line" d="M770,140 L440,250" marker-end="url(#a)"/>
<text x="660" y="186" class="lbl">plans, fact claims</text>
<path class="line" d="M955,140 V436" marker-end="url(#a)"/><text x="948" y="300" class="lbl" text-anchor="end">each step</text>
<rect class="box" x="20" y="440" width="420" height="140" rx="8"/>
<text x="36" y="468" class="t">GitHub</text><text x="36" y="494">Pages: this website and 100 LaTeX PDFs</text>
<text x="36" y="516">Repository: code, artifacts, run records</text><text x="36" y="538">Release: the demo video</text>
<path class="line" d="M676,306 V400 H230 V436" marker-end="url(#a)"/><text x="470" y="394" class="lbl">site/ → gh-pages</text>
<rect class="box" x="480" y="440" width="500" height="140" rx="8"/>
<text x="496" y="468" class="t">Hermes agent, on the laptop</text>
<text x="496" y="494">5 tools read the saved index, no GPU needed:</text>
<text x="496" y="516" class="m">search · compare · passages · scan · corpus</text>
<text x="496" y="538">plus vision_analyze to look at a scan</text>
<path class="line" d="M532,306 V436" marker-end="url(#a)"/><text x="540" y="424" class="lbl">index.json</text>
</svg>"""


def entry_figure(scan: Path, entries: list[dict[str, Any]], out: Path) -> bool:
    """Draw each entry's box and label on the scan. Return False when the scan is missing."""
    if not scan.exists():
        return False
    from PIL import Image, ImageDraw, ImageFont

    image = Image.open(scan).convert("RGB")
    image = image.resize((image.width * 3 // 2, image.height * 3 // 2), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image, "RGBA")
    try:
        font = ImageFont.truetype("Arial Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    for n, entry in enumerate(entries):
        colour = tuple(int(BOX_COLOURS[n % len(BOX_COLOURS)][i:i + 2], 16) for i in (1, 3, 5))
        for part in entry["source"]:
            if not part.get("bbox"):
                continue
            x0, y0, x1, y1 = (v * s for v, s in zip(part["bbox"], (image.width, image.height) * 2))
            draw.rectangle((x0, y0, x1, y1), outline=colour + (255,), width=3, fill=colour + (28,))
            tx = x0 - 34 if x0 > 40 else x0 + 4
            draw.rectangle((tx, y0 + 2, tx + 32, y0 + 28), fill=colour + (235,))
            draw.text((tx + 4, y0 + 3), f"e{n + 1}", fill=(255, 255, 255), font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, "JPEG", quality=75)
    return True


def topic_match(entry: dict[str, Any]) -> dict[str, Any]:
    return (entry.get("match") or {}).get("topic") or {}


def entry_section(index: dict[str, Any], site_dir: Path, scan_dir: Path) -> str:
    page_entries = sorted(((entry_id, entry) for entry_id, entry in index["entries"].items()
                           if entry_id.startswith(EXAMPLE_PAGE + ":")), key=lambda item: int(item[0].rsplit(":e", 1)[1]))
    if not page_entries:
        return ""
    drawn = entry_figure(Path(scan_dir) / f"{EXAMPLE_PAGE}.jpg", [entry for _, entry in page_entries],
                         site_dir / "figures" / "page-entries.jpg")
    rows = "".join(
        f"<li><span class=\"tag\" style=\"background:{BOX_COLOURS[n % len(BOX_COLOURS)]}\">e{n + 1}</span>"
        f"<b>{esc(entry['title'])}</b>{' (continuation)' if entry['kind'] == 'continuation' else ''}: "
        f"matched to {esc(topic_match(entry).get('title') or 'nothing')} "
        f"<span class=\"{esc(topic_match(entry).get('decision'))}\">{esc(topic_match(entry).get('decision'))}</span></li>"
        for n, (_, entry) in enumerate(page_entries))
    figure = (f"<img src=\"figures/page-entries.jpg\" alt=\"Scan {EXAMPLE_PAGE} with each entry outlined and labelled\">"
              if drawn else "")
    return (f"<h2>Page, entry and match</h2><dl class=\"defs\">"
            "<dt>Page</dt><dd>One scanned image. Most pages have two columns of text.</dd>"
            "<dt>Entry</dt><dd>One encyclopedia article: a headword in capitals and the text that explains it. A page "
            "usually holds several entries.</dd>"
            "<dt>Continuation</dt><dd>A piece of a long article that started on an earlier page, with no headword.</dd>"
            "<dt>Match</dt><dd>The Wikipedia article about the same subject as an entry. The pipeline compares what the "
            "two say, so it needs the whole article, not the meaning of one word.</dd></dl>"
            f"<p>Example: scan <a href=\"pages/{EXAMPLE_PAGE}.html\">{EXAMPLE_PAGE[:9]}</a> holds {len(page_entries)} entries. "
            "The boxes come from the block positions that Parse returned.</p>"
            f"<div class=\"entrygrid\"><div>{figure}</div><ul>{rows}</ul></div>"
            "<p class=\"muted\">Names change over time, so a match can have a different title, for example SWOONING and "
            "the article on syncope.</p>")


def matching_section(index: dict[str, Any], matches: dict[str, Any]) -> str:
    result = next((r for r in matches["results"] if r["entry_id"] == EXAMPLE_ENTRY and r["target"] == "topic"), None)
    entry = index["entries"].get(EXAMPLE_ENTRY)
    if result is None or entry is None:
        return ""
    plan = matches["plans"].get(EXAMPLE_ENTRY, {})
    ranked = "".join(
        f"<tr><td>{esc(row['title'])}{' (disambiguation, not eligible)' if row.get('navigation') else ''}</td>"
        f"<td>{row['embed_rank']}</td><td>{row['cosine']:.3f}</td><td>{row['rerank_logit']:.2f}</td></tr>"
        for row in result["ranked"][:6])
    searches = "".join(f"<li>{esc(query)}</li>" for query in result.get("searches", []))
    return (f"<h2>Finding the Wikipedia article: {esc(entry['title'])}</h2>"
            f"<p class=\"panel source\"><span class=\"label\">Britannica text, as Parse read it</span><br>"
            f"{esc(entry['text'][:260])}…</p>"
            "<h3>1. Super VL suggests what to look for</h3>"
            f"<p>Modern title: <b>{esc(plan.get('topic'))}</b>. Description: {esc(plan.get('topic_description'))}</p>"
            "<h3>2. Collect candidates</h3>"
            f"<p><b>Title lookup</b> asks Wikipedia for these exact names: {esc(', '.join(result.get('titles', [])))}. "
            "<b>Keyword search</b> sends each phrase below to the organizer's BM25 search engine, which returns the 20 "
            "articles that best contain its words. Rare words count more than common ones. It matches words, not meaning.</p>"
            f"<ul>{searches}</ul><p>Together they give <b>{esc(result.get('candidates'))}</b> different candidate articles.</p>"
            "<h3>3. Embedder and reranker</h3>"
            "<p>The embedder turns the entry (topic plus up to 1,100 characters of text) and each candidate (title plus its "
            "first 1,000 characters) into 2,048 numbers, and ranks the candidates by cosine similarity: 1 is the same meaning, "
            "0 is unrelated. The reranker then reads the entry and one candidate side by side and gives a more careful score "
            "to the top 32.</p>"
            "<table><tr><th>Candidate</th><th>Embedder rank</th><th>Similarity</th><th>Reranker score</th></tr>"
            f"{ranked}</table>"
            "<h3>4. A rule decides</h3>"
            f"<p>Decision: <span class=\"{esc(result['decision'])}\"><b>{esc(result['decision'])}</b></span>, "
            f"{esc(result['label'])} → {esc(result.get('title'))}. Reason: {esc(result['reason'])}. The limits come from "
            "540 candidates checked by hand.</p>")


def how_body(index: dict[str, Any], matches: dict[str, Any], comparison: dict[str, Any], site_dir: Path,
             scan_dir: Path) -> str:
    decisions = matches["counts"]["decisions"].get("topic", {})
    facts = index["corpus"].get("fact_counts") or {}
    verdicts = facts.get("verdicts", {})
    counts = comparison["counts"]
    return (
        "<p>The project has two phases. First, the pipeline reads the scans, matches each entry to Wikipedia, and "
        "compares them. This used the organizer servers, our GPU endpoint and Token Factory, and every result was saved "
        "in the repository. Then the Hermes agent answers questions from those saved files. It needs only Token Factory, "
        "not the GPU.</p>"
        "<h2>Architecture</h2>"
        f"<div class=\"arch\">{architecture_svg()}</div>"
        "<p class=\"muted\">Dashed lines: the GPU endpoint was used for matching and comparing, then deleted.</p>"
        + entry_section(index, site_dir, scan_dir)
        + "<h2>Reading a page</h2><ol>"
        "<li>Our code measures the ink, so blank pages, covers and picture plates are set aside before Parse can invent text on them.</li>"
        "<li>Parse reads the whole page once to find the layout: blocks of text with their position and type.</li>"
        "<li>Our code finds the gap between the columns, cuts the page into the header and each column, and enlarges them 3×. "
        "Parse reads each part again, so the columns do not mix and the small letters are readable.</li>"
        "<li>Our code starts a new entry at each headword. A page without a headword becomes one continuation entry.</li></ol>"
        + matching_section(index, matches)
        + "<h2>Comparing</h2>"
        f"<p>{counts.get('pairs')} matched pairs. Topic decisions: {decisions.get('accepted')} accepted, "
        f"{decisions.get('uncertain')} uncertain, {decisions.get('no_match')} no match.</p><ul>"
        f"<li><b>Words</b>: after {counts.get('long_s_changes'):,} recorded long-s fixes, which words each source uses more.</li>"
        "<li><b>Topics</b>: entries and articles grouped by meaning with the embedder.</li>"
        f"<li><b>Facts</b>: Super VL lists claims with a quote from each source, and our code checks that each quote exists. "
        f"{facts.get('claims')} claims: {verdicts.get('agrees')} agree, {verdicts.get('differs')} differ, "
        f"{verdicts.get('not_found')} not found in the saved Wikipedia text.</li></ul>"
        "<p><a href=\"analysis.html\">See the full analysis →</a></p>"
        "<h2>The agent</h2>"
        "<p>Hermes runs Super VL in a loop. Super VL picks a tool, Hermes runs it and returns the result, and this repeats "
        "until Super VL writes the answer. The tools read the saved files only.</p>"
        "<table><tr><th>Tool</th><th>What it does</th></tr>"
        "<tr><td>challenge_search</td><td>Finds entries by words in their title, matched article title and text.</td></tr>"
        "<tr><td>challenge_compare</td><td>One entry with its source, match, scores, word comparison and checked facts.</td></tr>"
        "<tr><td>challenge_passages</td><td>Passages from a saved Wikipedia article.</td></tr>"
        "<tr><td>challenge_scan</td><td>The scan and an enlarged picture of the entry, for the vision tool.</td></tr>"
        "<tr><td>challenge_corpus</td><td>Corpus numbers: distinctive words, topics, match counts.</td></tr></table>"
        "<p>The agent must cite every source, quote only verified facts, and say when the evidence is missing. "
        "<a href=\"agent.html\">See its three successes and three failures →</a></p>")
