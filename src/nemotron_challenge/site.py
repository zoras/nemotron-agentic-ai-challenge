"""Build the static website and the compiled LaTeX source documents.

Each scan gets a LaTeX document with two parts, as in templates/page.tex: the extracted historical text
and its source record. LuaLaTeX compiles them. Each scan also gets an HTML page that shows the image,
the extracted text, and the generated comparison in visibly separate panels. Index, analysis, and agent
pages link everything together.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

from .compare import readable

FONTS = ("STIX Two Text", "Latin Modern Roman")  # the first font that LuaLaTeX finds is used
LATEX = re.compile(r"([\\{}$&#^%~])")
REPO_URL = "https://github.com/prabeshsb/nemotron-agentic-ai-challenge"


def tex_escape(text: str) -> str:
    """Escape LaTeX specials, then turn Parse's markdown emphasis into LaTeX emphasis."""
    text = re.sub(r"\\(?:begin|end)\{tabular\}(?:\{[^}]*\})?|\\hline|\\multicolumn\{\d+\}\{[^}]*\}", " ", text)
    text = text.replace("\\\\", "\n").replace("&", " | ")
    special = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "#": r"\#",
               "^": r"\^{}", "%": r"\%", "~": r"\~{}"}
    text = LATEX.sub(lambda match: special[match.group(1)], text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\\textit{\1}", text)
    text = text.replace("*", r"\textasteriskcentered{}").replace("_", r"\_")
    return re.sub(r"<[^>]+>", "", text)


def tex_paragraphs(text: str) -> str:
    return "\n\n".join(tex_escape(re.sub(r"\s*\n\s*", " ", part).strip()) for part in re.split(r"\n{2,}", text) if part.strip())


def page_tex(record: dict[str, Any], entries: list[dict[str, Any]], extract_summary: dict[str, Any], font: str) -> str:
    """LaTeX source for one scan: the extracted text, then the source record."""
    stem = Path(record["filename"]).stem
    lines = [r"\documentclass[10pt]{article}", r"\usepackage[margin=2cm]{geometry}", r"\usepackage{fontspec}",
             rf"\setmainfont{{{font}}}", r"\usepackage[hidelinks]{hyperref}", r"\begin{document}",
             rf"\noindent{{\Large Encyclopaedia Britannica scan {tex_escape(stem)}}}\\[2pt]",
             rf"\noindent Running head as read: \textit{{{tex_escape(record.get('running_head') or 'none')}}}",
             r"\section*{Historical source}"]
    if entries:
        lines.append(r"\noindent\textit{Text as extracted by Nemotron Parse 3.5. OCR errors and the long s read as f are kept.}")
        for entry in entries:
            title = entry["title"] or "untitled continuation"
            kind = {"headword": "entry", "continuation": "continues from an earlier page"}[entry["kind"]]
            lines.append(rf"\subsection*{{{tex_escape(title)} \normalfont\small({kind})}}")
            lines.append(tex_paragraphs(entry["text"]))
            lines.append(rf"\par\noindent{{\footnotesize Entry {tex_escape(entry['entry_id'])}; blocks "
                         rf"{tex_escape(', '.join(b.split(':')[1] for part in entry['parts'] for b in part['block_ids']))}}}")
    elif record["status"] == "plate":
        lines.append(r"\noindent\textit{A plate. The layout pass read these labels; they are not checked.}")
        labels = [block["text"] for block in record["blocks"] if block["class"] in {"Caption", "Text", "Title", "Section-header"}]
        lines.append(tex_paragraphs("\n\n".join(labels)) or "No labels were read.")
    else:
        lines.append(rf"\noindent No text: the scan is classified as \textit{{{record['status']}}} from its ink. "
                     r"Parse invents text for such pages, so none is kept.")
    evidence = record.get("status_evidence", {})
    rows = [("Page ID", record["page_id"]), ("Dataset", f"{extract_summary['dataset']} at {extract_summary['dataset_revision']}"),
            ("Row index", str(record["row_index"])), ("Volume ID", record["volume_id"]), ("Image file", record["filename"]),
            ("Image SHA-256", record["image_sha256"]), ("Page status", record["status"]),
            ("Status evidence", ", ".join(f"{k} {v}" for k, v in evidence.items())),
            ("Extraction model", extract_summary["parse_model"]), ("Extraction code", extract_summary["code_revision"]),
            ("Raw replies", f"artifacts/extract/raw/{stem}/"),
            ("Regions", ", ".join(r["label"] for r in record.get("regions", []) if not r.get("superseded")) or "none")]
    lines.append(r"\section*{Source record}")
    lines.append(r"\begin{description}")
    lines += [rf"\item[{tex_escape(key)}] \texttt{{\small {tex_escape(value)}}}" if "SHA" in key or "code" in key
              else rf"\item[{tex_escape(key)}] {tex_escape(value)}" for key, value in rows]
    lines.append(r"\end{description}")
    lines.append(r"\end{document}")
    return "\n".join(lines) + "\n"


def lualatex() -> str | None:
    return shutil.which("lualatex") or ("/Library/TeX/texbin/lualatex" if Path("/Library/TeX/texbin/lualatex").exists() else None)


def pick_font(engine: str) -> str:
    """Return the first font in FONTS that LuaLaTeX can load. The probe runs outside the site directory."""
    with tempfile.TemporaryDirectory() as workdir:
        for font in FONTS:
            probe = Path(workdir) / "font-probe.tex"
            probe.write_text(f"\\documentclass{{article}}\\usepackage{{fontspec}}\\setmainfont{{{font}}}\\begin{{document}}x\\end{{document}}\n")
            if subprocess.run([engine, "-interaction=nonstopmode", "-halt-on-error", probe.name], cwd=workdir,
                              capture_output=True, timeout=120).returncode == 0:
                return font
    raise RuntimeError("LuaLaTeX found none of the fonts " + ", ".join(FONTS))


def compile_tex(engine: str, tex: Path) -> dict[str, Any]:
    result = subprocess.run([engine, "-interaction=nonstopmode", "-halt-on-error", tex.name], cwd=tex.parent,
                            capture_output=True, text=True, timeout=300)
    log = tex.with_suffix(".log").read_text(errors="replace") if tex.with_suffix(".log").exists() else ""
    return {"document": tex.stem, "exit_code": result.returncode, "missing_glyphs": log.count("Missing character"),
            "error": next((line for line in log.splitlines() if line.startswith("!")), None)}


CSS = """
:root{--bg:#fbf8f2;--fg:#1f1d1a;--muted:#6b645a;--line:#ddd5c8;--source:#fffdf8;--generated:#eef3f8;--accent:#8a5a2b;--link:#2b5a8a;--ok:#2e7d32;--warn:#b26a00;--bad:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#171513;--fg:#ece6dc;--muted:#a49b8e;--line:#3a352f;--source:#201d1a;--generated:#1b2430;--accent:#d7a46d;--link:#8fb8e6;--ok:#7bc47f;--warn:#e0a54b;--bad:#ef8a80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 Georgia,'Times New Roman',serif}
header,main,footer{max-width:1180px;margin:0 auto;padding:16px}header{border-bottom:1px solid var(--line)}
nav a{margin-right:14px}a{color:var(--link)}h1{font-size:1.7rem;margin:.3em 0}h2{font-size:1.3rem;margin-top:1.6em}h3{font-size:1.1rem;margin:.2em 0}
.muted{color:var(--muted);font-size:.9rem}.grid{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:20px}
@media (max-width:820px){.grid{grid-template-columns:1fr}}
.scan img{width:100%;height:auto;border:1px solid var(--line)}.panel{border:1px solid var(--line);border-radius:6px;padding:12px 14px;margin:12px 0}
.source{background:var(--source)}.generated{background:var(--generated)}.label{font:600 .72rem/1 system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.ocr{white-space:pre-wrap;font-size:.95rem}table{border-collapse:collapse;width:100%;font-size:.9rem;display:block;overflow-x:auto}
th,td{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}.accepted{color:var(--ok)}.uncertain{color:var(--warn)}.no_match{color:var(--bad)}
.stats{display:flex;flex-wrap:wrap;gap:12px}.stat{border:1px solid var(--line);border-radius:6px;padding:8px 12px;min-width:140px}.stat b{display:block;font-size:1.4rem}
img.figure{max-width:100%;height:auto;border:1px solid var(--line);background:#fff}details summary{cursor:pointer;color:var(--muted)}code{font-size:.85em}
"""


def page_html(title: str, body: str, depth: int = 0) -> str:
    up = "../" * depth
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{html.escape(title)}</title><link rel=\"stylesheet\" href=\"{up}style.css\"></head><body>"
            f"<header><nav><a href=\"{up}index.html\">Overview</a><a href=\"{up}scans.html\">Scans</a>"
            f"<a href=\"{up}analysis.html\">Analysis</a><a href=\"{up}agent.html\">Agent cases</a>"
            f"<a href=\"{REPO_URL}\">Repository</a></nav><h1>{html.escape(title)}</h1></header><main>{body}</main>"
            f"<footer class=\"muted\">Britannica scans: National Library of Scotland. Wikipedia text: CC BY-SA 4.0, "
            f"from the pinned wikimedia/structured-wikipedia snapshot. Generated comparisons are labelled as such.</footer></body></html>")


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def wiki_link(match: dict[str, Any]) -> str:
    if not match or not match.get("page_id"):
        return "none"
    url = match.get("url") or ""
    revision = match.get("revision_id")
    href = f"https://en.wikipedia.org/w/index.php?curid={match['page_id']}&oldid={revision}" if revision else url
    return f"<a href=\"{esc(href)}\">{esc(match.get('title'))}</a> <span class=\"muted\">page {esc(match['page_id'])}, revision {esc(revision)}</span>"


def comparison_panel(entry: dict[str, Any]) -> str:
    rows = []
    for target in ("topic", "subtopic"):
        match = entry.get("match", {}).get(target)
        if not match:
            continue
        rows.append(f"<tr><th>{target}: {esc(match.get('label'))}</th><td><span class=\"{esc(match.get('decision'))}\">"
                    f"{esc(match.get('decision'))}</span> → {wiki_link(match)}<br><span class=\"muted\">{esc(match.get('reason'))}"
                    f"{'; runner-up ' + esc(match.get('runner_up')) if match.get('runner_up') else ''}</span></td></tr>")
    vocabulary = entry.get("vocabulary")
    if vocabulary:
        rows.append(f"<tr><th>Vocabulary</th><td>{vocabulary['entry_coverage']:.0%} of the entry's content words appear in "
                    f"{esc(vocabulary['title'])} (unrelated articles: {vocabulary['baseline_coverage'] or 0:.0%}). "
                    f"Shared: {esc(', '.join(vocabulary['shared_words'][:10]))}. Entry only: {esc(', '.join(vocabulary['entry_only_words'][:10]))}.</td></tr>")
    facts = entry.get("facts") or []
    fact_rows = "".join(
        f"<tr><td>{esc(f['claim'])}</td><td class=\"{ 'accepted' if f['verdict']=='agrees' else 'no_match' if f['verdict']=='differs' else 'muted'}\">{esc(f['verdict'])}</td>"
        f"<td>“{esc(f.get('britannica_quote'))}” {'✓' if f.get('britannica_quote_found') else '✗ unverified'}</td>"
        f"<td>{('“' + esc(f.get('wikipedia_quote')) + '” ' + ('✓' if f.get('wikipedia_quote_found') else '✗ unverified')) if f.get('wikipedia_quote') else '—'}</td></tr>"
        for f in facts)
    table = f"<table>{''.join(rows)}</table>" if rows else "<p class=\"muted\">No match record.</p>"
    if fact_rows:
        table += ("<h3>Fact checks</h3><table><tr><th>Claim</th><th>Verdict</th><th>Britannica quote</th><th>Wikipedia quote</th></tr>"
                  f"{fact_rows}</table>")
    return f"<div class=\"panel generated\"><div class=\"label\">Generated comparison, not source text</div>{table}</div>"


def scan_page(record: dict[str, Any], entries: list[dict[str, Any]], index: dict[str, Any], prev_next: tuple[str | None, str | None],
              compiled: bool) -> str:
    stem = Path(record["filename"]).stem
    parts = [f"<p class=\"muted\">Page ID <code>{esc(record['page_id'])}</code> · status <b>{esc(record['status'])}</b> · "
             f"running head “{esc(record.get('running_head'))}” · SHA-256 <code>{esc(record['image_sha256'][:16])}…</code></p>",
             "<p>" + " · ".join(filter(None, [
                 f"<a href=\"{prev_next[0]}.html\">← previous scan</a>" if prev_next[0] else None,
                 f"<a href=\"../documents/{stem}.pdf\">Compiled LaTeX document (PDF)</a>" if compiled else "LaTeX document did not compile",
                 f"<a href=\"../documents/{stem}.tex\">LaTeX source</a>",
                 f"<a href=\"{REPO_URL}/tree/main/artifacts/extract/raw/{stem}\">raw Parse replies</a>",
                 f"<a href=\"{prev_next[1]}.html\">next scan →</a>" if prev_next[1] else None])) + "</p>",
             "<div class=\"grid\"><div class=\"scan\">"
             f"<a href=\"../scans/{esc(record['filename'])}\"><img src=\"../scans/{esc(record['filename'])}\" alt=\"Scan {esc(stem)}\" loading=\"lazy\"></a></div><div>"]
    if not entries:
        parts.append(f"<div class=\"panel source\"><div class=\"label\">Source</div><p>No entries: the scan is a {esc(record['status'])} page.</p></div>")
    for entry in entries:
        agent_entry = index["entries"].get(entry["entry_id"], {})
        notes = ", ".join(note["text"] for note in entry["margin_notes"][:5])
        parts.append(
            f"<section id=\"{esc(entry['entry_id'].split(':')[1])}\"><h3>{esc(entry['title'] or 'Untitled continuation')} "
            f"<span class=\"muted\">({esc(entry['kind'])}, {esc(entry['entry_id'].split(':')[1])})</span></h3>"
            f"<div class=\"panel source\"><div class=\"label\">Source text · Nemotron Parse 3.5 OCR</div><div class=\"ocr\">{esc(entry['text'])}</div>"
            f"{'<p class=muted>Margin notes: ' + esc(notes) + '</p>' if notes else ''}"
            f"<details><summary>Reading with the long s restored</summary><div class=\"ocr\">{esc(readable(entry['text']))}</div></details></div>"
            f"{comparison_panel(agent_entry)}</section>")
    parts.append("</div></div>")
    return page_html(f"Scan {stem}", "".join(parts), depth=1)


def run_site(work_dir: Path, site_dir: Path, scan_dir: Path, workers: int = 2) -> dict[str, Any]:
    work_dir, site_dir = Path(work_dir), Path(site_dir)
    extract_summary = json.loads((work_dir / "extract" / "summary.json").read_text(encoding="utf-8"))
    entries_doc = json.loads((work_dir / "extract" / "entries.json").read_text(encoding="utf-8"))
    index = json.loads((work_dir / "agent" / "index.json").read_text(encoding="utf-8"))
    comparison = json.loads((work_dir / "compare" / "comparison.json").read_text(encoding="utf-8"))
    matches = json.loads((work_dir / "match" / "matches.json").read_text(encoding="utf-8"))
    cases_path = work_dir / "evaluate" / "cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8")) if cases_path.exists() else None
    records = sorted((json.loads(p.read_text(encoding="utf-8")) for p in (work_dir / "extract" / "pages").glob("*.json")),
                     key=lambda r: r["row_index"])
    by_page: dict[str, list[dict[str, Any]]] = {}
    for entry in entries_doc["entries"]:
        by_page.setdefault(entry["parts"][0]["filename"], []).append(entry)

    for sub in ("pages", "scans", "documents", "figures"):
        (site_dir / sub).mkdir(parents=True, exist_ok=True)
    (site_dir / "style.css").write_text(CSS, encoding="utf-8")
    for figure in (work_dir / "compare" / "figures").glob("*.png"):
        shutil.copy2(figure, site_dir / "figures" / figure.name)
    for record in records:
        source = Path(scan_dir) / record["filename"]
        if source.exists():
            shutil.copy2(source, site_dir / "scans" / record["filename"])

    engine = lualatex()
    builds: list[dict[str, Any]] = []
    font = None
    if engine:
        font = pick_font(engine)
        texs = []
        for record in records:
            tex = site_dir / "documents" / f"{Path(record['filename']).stem}.tex"
            tex.write_text(page_tex(record, by_page.get(record["filename"], []), extract_summary, font), encoding="utf-8")
            texs.append(tex)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            builds = list(pool.map(lambda tex: compile_tex(engine, tex), texs))
        for leftover in (site_dir / "documents").iterdir():
            if leftover.suffix in {".aux", ".log", ".out"}:
                leftover.unlink()
    compiled = {build["document"] for build in builds if build["exit_code"] == 0}

    stems = [Path(record["filename"]).stem for record in records]
    for position, record in enumerate(records):
        stem = stems[position]
        neighbours = (stems[position - 1] if position else None, stems[position + 1] if position + 1 < len(stems) else None)
        (site_dir / "pages" / f"{stem}.html").write_text(
            scan_page(record, by_page.get(record["filename"], []), index, neighbours, stem in compiled), encoding="utf-8")

    decisions = matches["counts"]["decisions"]
    status = dict(Counter(record["status"] for record in records))
    rows = []
    for record in records:
        stem = Path(record["filename"]).stem
        page_entries = by_page.get(record["filename"], [])
        accepted = sum(1 for e in page_entries if index["entries"].get(e["entry_id"], {}).get("match", {}).get("topic", {}).get("decision") == "accepted")
        rows.append(f"<tr><td><a href=\"pages/{stem}.html\">{esc(stem[:9])}</a></td><td>{esc(record['status'])}</td>"
                    f"<td>{esc(record.get('running_head'))}</td><td>{len(page_entries)}</td><td>{accepted}</td></tr>")
    scans_html = page_html("All 100 scans", "<table><tr><th>Scan</th><th>Status</th><th>Running head</th><th>Entries</th>"
                           f"<th>Accepted topic matches</th></tr>{''.join(rows)}</table>")
    (site_dir / "scans.html").write_text(scans_html, encoding="utf-8")

    facts = index["corpus"].get("fact_counts") or {}
    stats = [("Scans", len(records)), ("Text pages", status.get("text", 0)), ("Entries", len(entries_doc["entries"])),
             ("Topic matches accepted", decisions.get("topic", {}).get("accepted", 0)),
             ("Distinct articles", matches["counts"]["articles_fetched"]), ("Fact claims checked", facts.get("claims", 0)),
             ("Compiled documents", len(compiled))]
    overview = (
        "<p>We extracted 100 scans of early Encyclopaedia Britannica editions (1768–1860) with Nemotron Parse 3.5, split them "
        "into entries, matched each entry to an English Wikipedia article, and compared vocabulary, topics and facts. "
        "Source text and generated comparisons are kept in separate, labelled panels.</p>"
        f"<div class=\"stats\">{''.join(f'<div class=stat><b>{v}</b>{esc(k)}</div>' for k, v in stats)}</div>"
        "<h2>Pipeline</h2><ol>"
        "<li><b>Extract</b>: a layout pass, then masked column crops at 3× through Nemotron Parse 3.5; pages classified by ink "
        "(cover, blank, plate, text) so that invented text on empty pages is dropped.</li>"
        "<li><b>Entries</b>: dictionary pages split at headwords; article pages give one continuing entry titled from the running head.</li>"
        "<li><b>Match</b>: Nemotron 3.5 Super VL reads the top of each scan and proposes modern titles and queries; titles resolve "
        "to page IDs, BM25 adds keyword candidates, the Nemotron embedder ranks them and the Nemotron reranker scores the top 32.</li>"
        "<li><b>Compare</b>: long-s folding and historical spellings recorded, vocabulary overlap against a baseline, distinctive words, "
        "a joint topic model on Nemotron embeddings, and Super VL fact checks with quotes verified against both texts.</li>"
        "<li><b>Agent</b>: Hermes with Super VL and five tools over the saved, cited artifacts.</li></ol>"
        f"<h2>Coverage</h2><p>Page status: {esc(dict(status))}. Topic decisions: {esc(decisions.get('topic'))}. "
        f"Subtopic decisions: {esc(decisions.get('subtopic'))}. Cross-page joins: {entries_doc['counts']['joined']} "
        "(no consecutive scans in the sample continue each other).</p>"
        "<p><a href=\"scans.html\">Browse all scans →</a></p>")
    (site_dir / "index.html").write_text(page_html("Knowledge across time: Britannica meets Wikipedia", overview), encoding="utf-8")

    words = comparison["distinctive_words"]["content_words"]
    topics = comparison.get("topics", {})
    topic_rows = "".join(f"<tr><td>{t['topic']}</td><td>{esc(t.get('label') or ', '.join(t['terms'][:6]))}</td><td>{t['britannica']}</td>"
                         f"<td>{t['wikipedia']}</td><td>{esc(', '.join(t['examples'][:4]))}</td></tr>" for t in topics.get("topics", []))
    change_rows = "".join(f"<tr><td>{esc(c['printed'])}</td><td>{esc(c['normalised'])}</td><td>{esc(c['rule'])}</td><td>{c['count']}</td></tr>"
                          for c in comparison["text_changes"][:30])
    omitted = [r for r in matches["results"] if r["target"] == "topic" and r["decision"] != "accepted"]
    omission_rows = "".join(f"<tr><td><a href=\"pages/{esc(r['entry_id'].split(':')[0])}.html#{esc(r['entry_id'].split(':')[1])}\">{esc(r['entry_id'])}</a></td>"
                            f"<td>{esc(r['label'])}</td><td class=\"{esc(r['decision'])}\">{esc(r['decision'])}</td><td>{esc(r.get('title'))}</td><td>{esc(r['reason'])}</td></tr>"
                            for r in omitted)
    repeated = "".join(f"<li>{esc(index['articles'].get(pid, {}).get('title', pid))}: {esc(', '.join(ids))}</li>"
                       for pid, ids in matches["repeated_selections"].items())
    analysis = (
        f"<p>{comparison['counts']['pairs']} accepted pairs, {comparison['counts']['britannica_tokens']:,} Britannica tokens and "
        f"{comparison['counts']['wikipedia_tokens']:,} Wikipedia tokens. Long-s changes: {comparison['counts']['long_s_changes']:,}; "
        f"historical spellings: {comparison['counts']['historical_spelling_changes']}; Britannica words unknown to wordfreq "
        f"(OCR errors or obsolete words, excluded from word counts): {comparison['counts']['britannica_unknown_tokens']:,}.</p>"
        "<h2>Words each source uses more</h2><img class=\"figure\" src=\"figures/distinctive-words.png\" alt=\"Distinctive words\">"
        "<p class=\"muted\">Content words, log-odds ratio with an informative Dirichlet prior (Monroe et al. 2008).</p>"
        f"<p>Britannica: {esc(', '.join(w['word'] for w in words['left'][:20]))}</p><p>Wikipedia: {esc(', '.join(w['word'] for w in words['right'][:20]))}</p>"
        "<h2>Vocabulary overlap</h2><img class=\"figure\" src=\"figures/vocabulary-overlap.png\" alt=\"Vocabulary overlap\">"
        f"<p>Median lift over unrelated articles: {esc(comparison['counts'].get('median_lift'))}.</p>"
        + ("<h2>Joint topics</h2><img class=\"figure\" src=\"figures/topics.png\" alt=\"Topic map\">"
           f"<p>Pairs whose entry and article fall in the same topic: {esc(topics.get('pair_topic_agreement'))}.</p>"
           f"<table><tr><th>Topic</th><th>c-TF-IDF terms</th><th>Britannica</th><th>Wikipedia</th><th>Examples</th></tr>{topic_rows}</table>"
           if topics else "")
        + f"<h2>Spelling normalisation</h2><table><tr><th>Printed</th><th>Read as</th><th>Rule</th><th>Count</th></tr>{change_rows}</table>"
        f"<h2>Repeated selections</h2><ul>{repeated or '<li>none</li>'}</ul>"
        f"<h2>Entries without an accepted topic match</h2><table><tr><th>Entry</th><th>Topic</th><th>Decision</th><th>Best candidate</th><th>Reason</th></tr>{omission_rows}</table>")
    (site_dir / "analysis.html").write_text(page_html("Comparison analysis", analysis), encoding="utf-8")

    if cases:
        case_html = (f"<p><b>Reviewer:</b> {esc(cases.get('reviewer'))}</p>"
                     + (f"<p><b>Scan ground truth:</b> {esc(cases['ground_truth_scans'])}</p>"
                        if cases.get("ground_truth_scans") else "")) + "".join(
            f"<section class=\"panel {'source' if c['classification'] == 'success' else 'generated'}\"><div class=\"label\">{esc(c['classification'])}</div>"
            f"<h3>{esc(c['case_id'])}: {esc(c['title'])}</h3><p><b>Question:</b> {esc(c['question'])}</p>"
            f"<p><b>What happened:</b> {esc(c['result'])}</p><p><b>Evidence:</b> {esc(c['evidence'])}</p>"
            f"<p><b>Limits:</b> {esc(c['limits'])}</p>"
            f"<p class=\"muted\">Run record: {esc(c['run_record'])}"
            + (f"<br>Repaired by: {esc(c['repaired_by'])}" if c.get("repaired_by") else "") + "</p></section>"
            for c in cases["cases"])
    else:
        case_html = "<p>The agent case studies have not been recorded yet.</p>"
    (site_dir / "agent.html").write_text(page_html("Hermes agent: three successes and three failures", case_html), encoding="utf-8")

    build = {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "engine": engine, "font": font,
             "documents": len(builds), "compiled": len(compiled),
             "failed": [b for b in builds if b["exit_code"] != 0],
             "missing_glyphs": sum(b["missing_glyphs"] for b in builds)}
    (site_dir / "build.json").write_text(json.dumps(build, indent=1), encoding="utf-8")
    return {k: build[k] for k in ("engine", "font", "documents", "compiled", "missing_glyphs")} | {"failed": len(build["failed"])}

