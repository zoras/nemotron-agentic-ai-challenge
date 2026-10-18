"""Build the agent index and run Hermes on a fixed question set.

The Hermes plugin in integrations/hermes reads artifacts/agent/index.json with the standard library only.
The index joins each entry with its source record, match decision, vocabulary comparison, and checked
facts. Runs call the installed `hermes` CLI and keep each transcript under artifacts/agent/runs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from .compare import readable

EVIDENCE_RULES = [
    "Answer only from tool results. Cite Britannica by entry_id and page_id, Wikipedia by title, page_id and revision_id.",
    "Quote a fact claim only when its quote_found flags are true; otherwise call it unverified.",
    "A match with decision 'uncertain' or 'no_match' is not evidence that the two sources describe the same topic.",
    "When no saved entry or article covers the question, say that the evidence is missing.",
    "OCR text can be wrong; check doubtful words against the scan with challenge_scan and the vision tool.",
    "Ask the vision tool to transcribe the printed words. Do not give it the OCR reading, because it can repeat it.",
]


TOOLSETS = "nemotron_challenge,vision"   # vision_analyze reads scan regions with the main model, Super VL
MAX_TURNS = 12        # tool-calling iterations per question
RUN_BUDGET_S = 600    # Hermes gets a wrap-up notice at 80% of this
CROP_SCALE = 4        # Super VL misread "ſtab" in a 265 px crop and read it at 4x (evaluation/vision_check.json)
CROP_MAX_SIDE = 2400  # limit for long continuation columns

PREAMBLE = ("Use the challenge_* tools. Follow the evidence_rules that challenge_compare returns. "
            "Cite every factual statement. Say so when the saved evidence does not answer the question. ")
QUESTIONS = [
    {"id": "q1-sydenham-facts", "prompt": PREAMBLE + "What does the early Britannica say about Thomas Sydenham, and "
     "which of its facts does the matched Wikipedia article confirm or contradict?"},
    {"id": "q2-language-change", "prompt": PREAMBLE + "Across the matched pairs, which words does the Britannica use "
     "far more than Wikipedia, and what do they show about how the language or the knowledge changed?"},
    {"id": "q3-abyssinia", "prompt": PREAMBLE + "How does the Britannica account of Abyssinia compare with Wikipedia? "
     "Name the pages and articles you rely on."},
    {"id": "q4-missing", "prompt": PREAMBLE + "What does the Britannica sample say about the steam locomotive?"},
    {"id": "q5-scan-check", "prompt": PREAMBLE + "Find the Britannica entry on the sword. Check one doubtful OCR word "
     "against the scan image, and report what the printed page shows."},
    {"id": "q6-uncertain", "prompt": PREAMBLE + "Which entries could not be matched with confidence, and why? "
     "Give two examples with their evidence."},
]


def union_box(boxes: list[list[float]]) -> list[float] | None:
    if not boxes:
        return None
    return [round(min(b[0] for b in boxes), 4), round(min(b[1] for b in boxes), 4),
            round(max(b[2] for b in boxes), 4), round(max(b[3] for b in boxes), 4)]


def pixel_region(bbox: list[float] | None, size: tuple[int, int] | None, pad: float = 0.01) -> list[int] | None:
    """Turn a page-fraction box into the [x1, y1, x2, y2] pixel region that Hermes' vision_analyze expects."""
    if bbox is None or size is None:
        return None
    width, height = size
    x0, y0, x1, y1 = max(0.0, bbox[0] - pad), max(0.0, bbox[1] - pad), min(1.0, bbox[2] + pad), min(1.0, bbox[3] + pad)
    return [int(x0 * width), int(y0 * height), int(round(x1 * width)), int(round(y1 * height))]


def write_crop(scan: Path, region: list[int], out: Path) -> float:
    """Save the entry region enlarged, so the vision model sees each printed letter at a readable size."""
    from PIL import Image

    crop = Image.open(scan).convert("RGB").crop(tuple(region))
    scale = max(1.0, min(CROP_SCALE, CROP_MAX_SIDE / max(crop.size)))
    crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.Resampling.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    crop.save(out, format="PNG")
    return round(scale, 2)


def source_part(part: dict[str, Any], boxes: dict[str, list[float]], sizes: dict[str, tuple[int, int]],
                scan_dir: Path, crop_dir: Path | None = None) -> dict[str, Any]:
    path = scan_dir / part["filename"]
    if part["filename"] not in sizes:
        from PIL import Image

        sizes[part["filename"]] = Image.open(path).size if path.exists() else None
    bbox = union_box([boxes[b] for b in part["block_ids"] if b in boxes])
    size = sizes[part["filename"]]
    region = pixel_region(bbox, size)
    crop_path, crop_scale = None, None
    if crop_dir is not None and region is not None:
        crop_path = crop_dir / f"{path.stem}-{'-'.join(map(str, region))}.png"
        crop_scale = write_crop(path, region, crop_path)
    return {**{k: part[k] for k in ("page_id", "filename", "image_sha256", "row_index", "block_ids")}, "bbox": bbox,
            "image_size": list(size) if size else None, "region_px": region,
            "crop_path": str(crop_path) if crop_path else None, "crop_scale": crop_scale}


def build_index(work_dir: Path, scan_dir: Path = Path("data/raw/britannica")) -> dict[str, Any]:
    """Join the saved artifacts into artifacts/agent/index.json and return its counts."""
    work_dir = Path(work_dir)
    sizes: dict[str, tuple[int, int] | None] = {}
    extract = json.loads((work_dir / "extract" / "entries.json").read_text(encoding="utf-8"))
    matches = json.loads((work_dir / "match" / "matches.json").read_text(encoding="utf-8"))
    comparison = json.loads((work_dir / "compare" / "comparison.json").read_text(encoding="utf-8"))
    facts_path = work_dir / "compare" / "facts.json"
    facts = json.loads(facts_path.read_text(encoding="utf-8")) if facts_path.exists() else {"pairs": []}
    boxes = {}
    for path in (work_dir / "extract" / "pages").glob("*.json"):
        for block in json.loads(path.read_text(encoding="utf-8"))["blocks"]:
            boxes[block["id"]] = block["bbox"]
    vocabulary = {row["target_id"]: row for row in comparison["pairs"]}
    claims = {row["entry_id"]: row for row in facts["pairs"]}
    keep = ("decision", "reason", "title", "page_id", "rerank_logit", "margin", "title_support")
    entries = {}
    for entry in extract["entries"]:
        entry_id = entry["entry_id"]
        plan = matches["plans"].get(entry_id, {})
        match = {}
        for result in matches["results"]:
            if result["entry_id"] == entry_id:
                ranked = {row["page_id"]: row for row in result["ranked"]}
                chosen = ranked.get(result.get("page_id"), {})
                match[result["target"]] = {**{k: result.get(k) for k in keep}, "label": result["label"],
                                           "revision_id": chosen.get("revision_id"), "url": chosen.get("url"),
                                           "text_sha256": chosen.get("text_sha256"),
                                           "runner_up": next((row["title"] for row in result["ranked"]
                                                              if row["page_id"] != result.get("page_id")), None)}
        pair = vocabulary.get(f"{entry_id}#subtopic") or vocabulary.get(f"{entry_id}#topic")
        fact_row = claims.get(entry_id, {})
        entries[entry_id] = {
            "title": entry["title"], "topic": plan.get("topic"), "kind": entry["kind"], "page_type": entry["page_type"],
            "source": [source_part(part, boxes, sizes, scan_dir, work_dir / "agent" / "crops") for part in entry["parts"]],
            "margin_notes": [note["text"] for note in entry["margin_notes"]],
            "text": entry["text"], "text_normalised": readable(entry["text"]),
            "match": match,
            "vocabulary": {k: pair[k] for k in ("title", "entry_coverage", "baseline_coverage", "lift", "shared_words",
                                                "entry_only_words", "entry_unknown_rate")} if pair else None,
            "facts": [{**claim, "article": fact_row.get("article_title"), "page_id": fact_row.get("page_id"),
                       "revision_id": fact_row.get("revision_id")} for claim in fact_row.get("claims", [])],
        }
    articles = {}
    for path in sorted((work_dir / "match" / "articles").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        articles[data["page_id"]] = {k: data[k] for k in ("title", "url", "revision_id", "text_sha256")} | {
            "path": str(path.relative_to(work_dir.parent)) if work_dir.is_absolute() else str(path)}
    topics = comparison.get("topics", {})
    corpus = {
        "match_counts": matches["counts"], "comparison_counts": comparison["counts"],
        "fact_counts": facts.get("counts"),
        "words_britannica_uses_more": [row["word"] for row in comparison["distinctive_words"]["content_words"]["left"][:20]],
        "words_wikipedia_uses_more": [row["word"] for row in comparison["distinctive_words"]["content_words"]["right"][:20]],
        "spelling_changes": comparison["text_changes"][:25],
        "topics": topics.get("topics", []), "pair_topic_agreement": topics.get("pair_topic_agreement"),
        "repeated_selections": matches["repeated_selections"],
    }
    index = {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "evidence_rules": EVIDENCE_RULES,
             "entries": entries, "articles": articles, "corpus": corpus}
    out = work_dir / "agent"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return {"entries": len(entries), "articles": len(articles),
            "entries_with_facts": sum(1 for e in entries.values() if e["facts"])}


def find_hermes() -> str | None:
    """The installer puts hermes in ~/.local/bin, which a non-login shell may not have on PATH."""
    found = shutil.which("hermes")
    fallback = Path.home() / ".local" / "bin" / "hermes"
    return found or (str(fallback) if fallback.exists() else None)


def read_events(stdout: str) -> dict[str, Any]:
    """Collect the model, tool calls, and final answer from `hermes chat --format stream-json` output."""
    events = []
    for line in stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    calls, pending = [], []
    for event in events:
        if event.get("type") == "tool_use":
            pending.append({"name": event.get("name"), "input": event.get("input")})
        elif event.get("type") == "tool_result":
            call = pending.pop(0) if pending else {"name": event.get("name"), "input": None}
            calls.append({**call, "output": event.get("output"), "is_error": event.get("is_error"),
                          "duration_ms": event.get("duration_ms")})
    calls += [{**call, "output": None, "is_error": None, "duration_ms": None} for call in pending]
    init = next((e for e in events if e.get("type") == "system"), {})
    result = next((e for e in events if e.get("type") == "result"), {})
    return {"model": init.get("model"), "session_id": init.get("session_id") or result.get("session_id"),
            "tool_calls": calls, "answer": result.get("text"), "tokens": result.get("tokens"),
            "duration_ms": result.get("duration_ms"), "events": len(events)}


def sync_plugin(hermes_home: Path, source: Path = Path("integrations/hermes/nemotron-challenge")) -> None:
    """Copy the repository's plugin into the Hermes profile, so runs use the committed tool code."""
    target = hermes_home / "plugins" / source.name
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))


def run_question(question: dict[str, str], out_dir: Path, hermes_home: Path, timeout: int = 900) -> dict[str, Any]:
    """Ask Hermes one question in a fresh one-shot session and keep the transcript.

    stream-json output records each tool call with its input and result, so the run can be checked
    against the saved evidence."""
    hermes = find_hermes()
    if hermes is None:
        raise RuntimeError("the hermes CLI is not installed; see docs/hermes.md")
    env = {**os.environ, "HERMES_HOME": str(hermes_home.resolve()), "NEMOTRON_CHALLENGE_REPO": str(Path.cwd())}
    version = subprocess.run([hermes, "--version"], capture_output=True, text=True, env=env).stdout.splitlines()
    command = [hermes, "chat", "--oneshot", "-t", TOOLSETS, "--format", "stream-json",
               "--max-turns", str(MAX_TURNS), "--run-budget", str(RUN_BUDGET_S), "--source", "tool",
               "-q", question["prompt"]]
    started = datetime.now(timezone.utc)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, env=env, timeout=timeout)
        stdout, stderr, code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code = exc.stdout or "", f"timed out after {timeout} s", None
        stdout = stdout.decode() if isinstance(stdout, bytes) else stdout
    record = {"question_id": question["id"], "question": question["prompt"],
              "hermes_version": version[0] if version else None, "command": command[:-1] + ["<prompt>"],
              "started_at": started.isoformat(timespec="seconds"),
              "elapsed_s": round((datetime.now(timezone.utc) - started).total_seconds(), 1),
              "exit_code": code, **read_events(stdout), "stdout": stdout, "stderr": stderr[-4000:]}
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    (out_dir / f"{question['id']}-{stamp}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return record
