"""Native Hermes tools for comparing Britannica entries with their matched Wikipedia articles.

The tools read the agent index that `nemotron-challenge run agent` builds from saved artifacts
(artifacts/agent/index.json). They use the Python standard library only, because Hermes runs in its own
environment. Every result names its sources: Britannica page IDs, scan checksums and block IDs, and
Wikipedia page IDs, revisions and text checksums. A tool returns an error object instead of raising.
"""
from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import re
from typing import Any

WORD = re.compile(r"[^\W\d_]+")
STOP = frozenset("""a about above after again against all also am an and any are as at be because been before being
below between both but by can could did do does doing down during each few for from further had has have having he her
here hers him his how i if in into is it its itself just me more most my no nor not of off on once only or other our out
over own same she should so some such than that the their them then there these they this those through to too under
until up very was we were what when where which while who whom why will with would you your""".split())


def repo() -> Path:
    return Path(os.environ.get("NEMOTRON_CHALLENGE_REPO", os.getcwd()))


_INDEX: dict[str, Any] = {}


def index() -> dict[str, Any]:
    path = repo() / "artifacts" / "agent" / "index.json"
    stamp = path.stat().st_mtime
    if _INDEX.get("stamp") != stamp:
        _INDEX.update(json.loads(path.read_text(encoding="utf-8")), stamp=stamp)
    return _INDEX


def words(text: str) -> list[str]:
    return [word for word in WORD.findall(text.lower()) if word not in STOP and len(word) > 2]


def result(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def guarded(handler):
    def run(params: dict[str, Any], **kwargs: Any) -> str:
        try:
            return result(handler(params or {}))
        except FileNotFoundError as exc:
            return result({"error": f"saved artifact is missing: {exc.filename}. Run `nemotron-challenge run agent`."})
        except Exception as exc:  # a tool must answer with an error object, never raise
            return result({"error": f"{type(exc).__name__}: {exc}"})
    return run


def search(params: dict[str, Any]) -> dict[str, Any]:
    query = str(params.get("query", "")).strip()
    limit = max(1, min(int(params.get("limit", 5)), 10))
    terms = Counter(words(query))
    if not terms:
        return {"error": "give a query with at least one content word"}
    scored = []
    for entry_id, entry in index()["entries"].items():
        title = Counter(words(" ".join(filter(None, [entry["title"], entry.get("topic")]))))
        article = Counter(words((entry.get("match", {}).get("topic") or {}).get("title") or ""))
        body = Counter(words(entry["text_normalised"]))
        score = sum(3 * title[t] + 2 * article[t] + min(body[t], 3) for t in terms)
        if score:
            scored.append((score, entry_id))
    rows = []
    for score, entry_id in sorted(scored, key=lambda item: (-item[0], item[1]))[:limit]:
        entry = index()["entries"][entry_id]
        rows.append({"entry_id": entry_id, "title": entry["title"], "topic": entry.get("topic"), "score": score,
                     "matched_article": (entry.get("match", {}).get("topic") or {}).get("title"),
                     "decision": (entry.get("match", {}).get("topic") or {}).get("decision"),
                     "snippet": entry["text_normalised"][:200]})
    return {"query": query, "results": rows,
            "note": "No saved entry matches these words." if not rows else "Call challenge_compare with an entry_id."}


def compare(params: dict[str, Any]) -> dict[str, Any]:
    entry_id = str(params.get("entry_id", "")).strip()
    entry = index()["entries"].get(entry_id)
    if entry is None:
        return {"error": f"unknown entry_id {entry_id!r}; call challenge_search first"}
    excerpt = int(params.get("excerpt_chars", 1500))
    return {
        "entry_id": entry_id,
        "britannica": {"title": entry["title"], "kind": entry["kind"], "page_type": entry["page_type"],
                       "source": entry["source"], "margin_notes": entry["margin_notes"][:6],
                       "text_ocr": entry["text"][:excerpt], "text_normalised": entry["text_normalised"][:excerpt],
                       "chars": len(entry["text"])},
        "match": entry.get("match", {}),
        "vocabulary": entry.get("vocabulary"),
        "facts": entry.get("facts", []),
        "evidence_rules": index()["evidence_rules"],
    }


def passages(params: dict[str, Any]) -> dict[str, Any]:
    page_id = str(params.get("page_id", "")).strip()
    article = index()["articles"].get(page_id)
    if article is None:
        return {"error": f"page_id {page_id!r} is not a saved matched article"}
    data = json.loads((repo() / article["path"]).read_text(encoding="utf-8"))
    terms = set(words(str(params.get("query", ""))))
    limit = max(1, min(int(params.get("limit", 3)), 6))
    offset, rows = 0, []
    for paragraph in data["text"].split("\n"):
        start = data["text"].find(paragraph, offset)
        offset = start + len(paragraph)
        if len(paragraph) < 80:
            continue
        hits = len(terms & set(words(paragraph)))
        rows.append((hits, start, paragraph))
    best = sorted(rows, key=lambda row: (-row[0], row[1]))[:limit] if terms else rows[:limit]
    return {"page_id": page_id, "title": data["title"], "revision_id": data["revision_id"], "url": data["url"],
            "text_sha256": data["text_sha256"],
            "passages": [{"offset": start, "matched_terms": hits, "text": text[:1500]} for hits, start, text in best]}


def scan(params: dict[str, Any]) -> dict[str, Any]:
    entry_id = str(params.get("entry_id", "")).strip()
    entry = index()["entries"].get(entry_id)
    if entry is None:
        return {"error": f"unknown entry_id {entry_id!r}"}
    rows = []
    for part in entry["source"]:
        path = repo() / "data" / "raw" / "britannica" / part["filename"]
        crop = repo() / part["crop_path"] if part.get("crop_path") else None
        rows.append({"page_id": part["page_id"], "image_path": str(path), "exists": path.exists(),
                     "image_sha256": part["image_sha256"], "image_size": part.get("image_size"),
                     "region": part.get("region_px"), "entry_bbox": part["bbox"],
                     "crop_path": str(crop) if crop else None, "crop_exists": bool(crop and crop.exists()),
                     "crop_scale": part.get("crop_scale"),
                     "note": "call vision_analyze with image_url=crop_path and no region: crop_path is the entry region "
                             "of the page, enlarged crop_scale times. Ask for a letter-by-letter transcription with "
                             "long s written as ſ. Do not put the OCR reading or candidate words in the question, "
                             "because the model can repeat them. If crop_path is null, use image_path with region "
                             "(pixels)."})
    return {"entry_id": entry_id, "scans": rows}


def corpus(params: dict[str, Any]) -> dict[str, Any]:
    del params
    return index()["corpus"]


def schema(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}


TOOLS = [
    (schema("challenge_search", "Find Britannica entries (1768-1860 editions) by topic words. Returns entry IDs, "
            "the matched Wikipedia article, and the match decision.",
            {"query": {"type": "string", "minLength": 1, "maxLength": 300},
             "limit": {"type": "integer", "minimum": 1, "maximum": 10}}, ["query"]), search),
    (schema("challenge_compare", "Return one Britannica entry with its source record, its Wikipedia match and the "
            "match evidence, the vocabulary comparison, and checked fact claims with quotes from both sources.",
            {"entry_id": {"type": "string", "minLength": 3, "maxLength": 80},
             "excerpt_chars": {"type": "integer", "minimum": 200, "maximum": 6000}}, ["entry_id"]), compare),
    (schema("challenge_passages", "Return passages of a matched Wikipedia article that contain the query words, "
            "with character offsets, revision, and text checksum for citation.",
            {"page_id": {"type": "string", "pattern": "^[0-9]{1,20}$"}, "query": {"type": "string", "maxLength": 300},
             "limit": {"type": "integer", "minimum": 1, "maximum": 6}}, ["page_id"]), passages),
    (schema("challenge_scan", "Return the scan image path, the entry's box on the page, and an enlarged crop of the "
            "entry, so the vision tool can check the OCR text against the printed page.",
            {"entry_id": {"type": "string", "minLength": 3, "maxLength": 80}}, ["entry_id"]), scan),
    (schema("challenge_corpus", "Return corpus-level results: words each source uses more, topic clusters, "
            "spelling normalisation counts, and match coverage.", {}, []), corpus),
]


def register(ctx: Any) -> None:
    """Register the comparison tools through the native Hermes interface."""
    for tool_schema, handler in TOOLS:
        ctx.register_tool(name=tool_schema["name"], toolset="nemotron_challenge", schema=tool_schema,
                          handler=guarded(handler))
