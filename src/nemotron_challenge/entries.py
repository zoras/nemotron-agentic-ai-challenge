"""Split extracted pages into source entries and join entries that run onto the next scan.

Two page types occur in the sample. Dictionary pages carry guide words in the running head
("SWI [ 248 ] SYD") and many short entries that start with a capitalised headword. Article pages
carry the title of one long article ("ABYSSINIA. 57"). Text before the first headword continues
an entry from an earlier page.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

ENTRY_CLASSES = {"Text", "List-item", "Section-header", "Title", "Footnote", "Table", "Formula"}
NOTE_CLASSES = {"Margin-note", "Caption"}
SPACED = re.compile(r"\b(?:[A-Z]\.? )+[A-Z]\b")            # letter-spaced capitals: "S W I", "A B Y S S"
STRAY_BRACKET = re.compile(r"(\d)\s*[JI]\s*(?=[A-Z]{3}\b)")  # "[ 752 JRES": Parse reads "]" as J or I
GUIDE_BRACKET = re.compile(r"(?:\b([A-Z]{2,4})\.?\s*)?[\[(|{]\s*\d[\d ]*[\])|}]?\s*(?:\b([A-Z]{2,4})\b)?")
GUIDE_PLAIN = re.compile(r"\b([A-Z]{2,4})\s+\d{1,4}\s*[\])|}]?\s+([A-Z]{2,4})\b")
CAPS_PHRASE = re.compile(r"[A-Z][A-Z'’-]+(?:\s+[A-Z][A-Z'’-]*)*")
HEADWORD = re.compile(r"^[#*\s]*([A-Z][A-Z'’-]+(?:\s+[A-Z][A-Z'’-]+)*)(?![a-z])\**\s*(\([^)]{1,60}\))?")
SEE = re.compile(r"\bS[ec]{2}\s+(?:also\s+)?([A-Z][A-Za-z'-]+)")
NOT_HEADWORDS = {"SECT", "CHAP", "PART", "BOOK", "ART", "PROP", "PROB", "FIG", "FIGS", "PLATE", "THEOR", "COR",
                 "SCHOL", "SCHOLIUM", "EXAMPLE", "EXP", "OBS", "DEM", "VOL", "NO", "THE", "OF", "AND"}
SHORT_WORDS = {"OF", "IN", "ON", "TO", "AN", "OR", "AT", "BY", "A"}
SAME_LETTER = str.maketrans("JV", "IU")  # the early editions file I with J and U with V
HEAD_ZONE = 0.1          # blocks centred above this share of the page height can be stray head text
MIN_HEADWORDS = 3        # a page without a readable head is a dictionary page with this many headwords
CROSS_REFERENCE_CHARS = 200
MARGIN_TITLE_ZONE = 0.12  # a short margin note this close to the top names the article on the page
MARGIN_WIDTH = 0.15       # margin notes are narrower than this share of the page width
MERGED_NAME = re.compile(r"^[#*_\s]*([A-Z][a-z]{2,})[*_]*\.[*_]*\s")
SEE_SKIP = {"Vol", "Part", "Plate", "Fig"}


def collapse(text: str) -> str:
    """Remove markdown marks and the spaces inside letter-spaced capitals."""
    text = text.replace("*", "").replace("_", "")
    text = SPACED.sub(lambda match: match.group(0).replace(" ", ""), text)
    return STRAY_BRACKET.sub(r"\1 ] ", text)


def doubled_guide(token: str) -> list[str] | None:
    """Read 'THOTHR' or 'NAZNAZNAZ' as guide words that Parse printed without a space."""
    if len(token) in (6, 9) and token[:2] == token[3:5]:
        return [token[:3], token[-3:]]
    return None


def title_phrase(text: str) -> str | None:
    """Return the capitalised phrase that holds the longest word, joining split words ('CONCHOLO GY')."""
    phrases = CAPS_PHRASE.findall(text)
    if not phrases:
        return None
    words = max(phrases, key=lambda phrase: max(len(word) for word in phrase.split())).split()
    merged: list[str] = []
    for word in words:
        if merged and len(word) <= 2 and word not in SHORT_WORDS:
            merged[-1] += word
        else:
            merged.append(word)
    return " ".join(merged).strip(".-'’ ")


def read_head(running_head: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify a page as a dictionary page, an article page, or unknown from its running head."""
    head = collapse(running_head)
    tokens = re.findall(r"[A-Z][A-Z'’-]+", head)
    long_words = [token for token in tokens if len(token) >= 5 and not doubled_guide(token)]
    if long_words:
        return {"page_type": "article", "head_title": title_phrase(head), "guide_words": [], "evidence": "running head title"}
    for pattern in (GUIDE_BRACKET, GUIDE_PLAIN):
        for match in pattern.finditer(head):
            words = [word for word in match.groups() if word]
            if words:
                return {"page_type": "dictionary", "head_title": None, "guide_words": words, "evidence": "running head guide words"}
    for token in tokens:
        if doubled_guide(token):
            return {"page_type": "dictionary", "head_title": None, "guide_words": doubled_guide(token),
                    "evidence": "running head guide words without spaces"}
    stray = [collapse(block["text"]).strip(" .") for block in blocks if is_head_debris(block)]
    stray = [text for text in stray if re.fullmatch(r"[A-Z]{3}", text)]
    if stray:
        return {"page_type": "dictionary", "head_title": None, "guide_words": stray[:2], "evidence": "guide words in column tops"}
    if len(tokens) == 1 and len(tokens[0]) >= 3 and head.rstrip().endswith("."):
        return {"page_type": "article", "head_title": tokens[0], "guide_words": [], "evidence": "running head title"}
    return {"page_type": "unknown", "head_title": None, "guide_words": [], "evidence": "running head not readable"}


def is_head_debris(block: dict[str, Any]) -> bool:
    """Short text without lower-case letters at the top of a column is a piece of the running head."""
    _, y0, _, y1 = block["bbox"]
    return (y0 + y1) / 2 < HEAD_ZONE and len(block["text"]) < 20 and not re.search(r"[a-z]", block["text"])


def headword(block: dict[str, Any]) -> tuple[str, str] | None:
    """Return (headword, heading) when a block starts with a capitalised headword."""
    match = HEADWORD.match(block["text"])
    if not match:
        return None
    word = match.group(1).strip("'’-")
    first = re.split(r"[\s-]", word)[0]
    if len(first) < 2 or first in NOT_HEADWORDS or re.fullmatch(r"[IVXLCDM]+", first):
        return None
    heading = f"{word} {match.group(2)}" if match.group(2) else word
    return word, heading


def initial(word: str) -> str:
    return word[:1].translate(SAME_LETTER)


def margin_title(notes: list[dict[str, Any]]) -> str | None:
    """Old editions print the article name in the outer margin at the top of each page.

    Parse can merge it with the next note ("Huefa\\nHuet", "Comines 1 Comitia"), so keep the first name only.
    """
    for note in notes:
        x0, y0, x1, _ = note["bbox"]
        if y0 >= MARGIN_TITLE_ZONE or x1 - x0 >= MARGIN_WIDTH:
            continue
        text = re.sub(r"<[^>]+>", "", collapse(note["text"]))
        text = re.sub(r"-\s+", "", text)
        name = re.split(r"[\n\d]", text)[0].strip(" .,;:∗")
        if name[:1].isupper() and len(name.split()) <= 2 and not re.match(r"(Fig|Plate|Vol)\b", name):
            return name
    return None


def merged_title(block: dict[str, Any], guide_words: list[str]) -> str | None:
    """Return a margin name that Parse merged into the first line ("**Nile.** or White River")
    when it agrees with the guide word. Long s is read as f, so compare with f folded to s."""
    match = MERGED_NAME.match(block["text"])
    guide = next((word for word in guide_words if len(word) >= 3), "")
    if not match or not guide:
        return None
    name = match.group(1)
    return name if name.upper().replace("F", "S").startswith(guide.replace("F", "S")) else None


def norm_title(title: str | None) -> str:
    return re.sub(r"[^A-Z]", "", (title or "").upper())


def page_entries(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Split one text page into entries. Return the entries and the page's segmentation record."""
    stem = Path(record["filename"]).stem
    blocks = record["blocks"]
    head = read_head(record.get("running_head", ""), blocks)
    body = [block for block in blocks if block["class"] in ENTRY_CLASSES and not is_head_debris(block)]
    body_ids = {block["id"] for block in body}
    note_ids = {block["id"] for block in blocks if block["class"] in NOTE_CLASSES}
    starts: dict[str, tuple[str, str]] = {}
    if head["page_type"] != "article":
        found = {block["id"]: hit for block in body if (hit := headword(block))}
        letters = Counter(initial(word) for word in head["guide_words"] if len(word) >= 3)
        letters.update(initial(word) for word, _ in found.values())
        letter = letters.most_common(1)[0][0] if letters else ""
        found = {block_id: hit for block_id, hit in found.items() if initial(hit[0]) == letter}
        if head["page_type"] == "dictionary" or len(found) >= MIN_HEADWORDS:
            starts = found
            if head["page_type"] == "unknown":
                head = {**head, "page_type": "dictionary", "evidence": f"{len(found)} headwords"}
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    pending_notes: list[dict[str, Any]] = []
    for block in blocks:
        if block["id"] in note_ids:
            (current["notes"] if current else pending_notes).append(block)
            continue
        if block["id"] not in body_ids:
            continue
        if current is None or block["id"] in starts:
            hit = starts.get(block["id"])
            current = {"kind": "headword" if hit else "continuation", "title": hit[0] if hit else None,
                       "heading": hit[1] if hit else None, "title_source": "headword" if hit else None,
                       "blocks": [], "notes": pending_notes}
            pending_notes = []
            entries.append(current)
        current["blocks"].append(block)
    if entries and entries[0]["kind"] == "continuation":
        first = entries[0]
        for source, title in (("running_head", head["head_title"]), ("margin_note", margin_title(first["notes"])),
                              ("merged_margin_note", merged_title(first["blocks"][0], head["guide_words"]))):
            if title:
                first["title"], first["title_source"] = title, source
                break
    page = {"page_id": record["page_id"], "filename": record["filename"], "image_sha256": record["image_sha256"],
            "row_index": record["row_index"], "volume_id": record["volume_id"]}
    out = []
    for number, entry in enumerate(entries, 1):
        text = "\n\n".join(block["text"] for block in entry["blocks"])
        out.append({
            "entry_id": f"{stem}:e{number}", "kind": entry["kind"], "title": entry["title"],
            "heading": entry["heading"], "title_source": entry["title_source"],
            "page_type": head["page_type"], "guide_words": head["guide_words"],
            "see": [word for word in SEE.findall(text) if word not in SEE_SKIP] if len(text) < CROSS_REFERENCE_CHARS else [],
            "starts_on_earlier_page": entry["kind"] == "continuation",
            "may_continue": number == len(entries),
            "parts": [{**page, "block_ids": [block["id"] for block in entry["blocks"]]}],
            "margin_notes": [{"block_id": note["id"], "text": note["text"]} for note in entry["notes"]],
            "text": text,
        })
    excluded = Counter()
    for block in blocks:
        if block["id"] not in body_ids:
            excluded["Head-debris" if block["class"] in ENTRY_CLASSES else block["class"]] += len(block["text"])
    segmentation = {"page_id": record["page_id"], "filename": record["filename"], **head,
                    "page_number": page_number(record.get("running_head", "")),
                    "entries": len(out), "headwords": len(starts),
                    "entry_chars": sum(len(entry["text"]) for entry in out),
                    "excluded_chars": dict(excluded)}
    return out, segmentation


def page_number(running_head: str) -> int | None:
    """Return the printed page number when the running head holds exactly one number."""
    numbers = set(re.findall(r"\b\d{1,4}\b", collapse(running_head)))
    return int(numbers.pop()) if len(numbers) == 1 else None


def can_join(before: dict[str, Any], after: dict[str, Any], numbers: tuple[int | None, int | None]) -> tuple[bool, str]:
    """Decide whether the first entry of a scan continues the last entry of the scan before it.

    Consecutive dataset rows are not always consecutive pages (rows 2569 and 2570 are pages 57 and 88
    of one volume), so the printed page numbers must follow each other before titles are compared.
    """
    if None in numbers or numbers[1] != numbers[0] + 1:
        return False, f"printed page numbers do not follow each other: {numbers[0]} / {numbers[1]}"
    if after["kind"] != "continuation":
        return False, f"next scan starts with the headword {after['title']}"
    left, right = norm_title(before["title"]), norm_title(after["title"])
    if left and right:
        return (left == right, f"titles {'match' if left == right else 'differ'}: {before['title']} / {after['title']}")
    guide = next((word for word in after["guide_words"] if len(word) >= 3), "")
    if left and guide:
        joined = left.startswith(norm_title(guide))
        return joined, f"guide word {guide} {'matches' if joined else 'does not match'} {before['title']}"
    return False, "no title or guide word to compare"


def build_entries(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Split every text page into entries and join entries across consecutive scans of one volume."""
    by_row = {record["row_index"]: record for record in records}
    per_page: dict[int, list[dict[str, Any]]] = {}
    pages = []
    for record in sorted(records, key=lambda record: record["row_index"]):
        if record["status"] not in {"text", "partial"}:
            pages.append({"page_id": record["page_id"], "filename": record["filename"], "page_type": record["status"],
                          "entries": 0, "evidence": f"page status {record['status']}"})
            continue
        entries, segmentation = page_entries(record)
        per_page[record["row_index"]] = entries
        pages.append(segmentation)
    joins = []
    for row, record in sorted(by_row.items()):
        following = by_row.get(row + 1)
        if not following or following["volume_id"] != record["volume_id"] or row not in per_page:
            continue
        before = per_page[row][-1] if per_page[row] else None
        after_entries = per_page.get(row + 1, [])
        if before is None or not after_entries:
            joins.append({"from": record["filename"], "to": following["filename"], "joined": False,
                          "reason": f"next scan is {following['status']}"})
            continue
        joined, reason = can_join(before, after_entries[0], (page_number(record.get("running_head", "")),
                                                             page_number(following.get("running_head", ""))))
        joins.append({"from": record["filename"], "to": following["filename"], "joined": joined, "reason": reason})
        if joined:
            after = after_entries.pop(0)
            before["parts"] += after["parts"]
            before["margin_notes"] += after["margin_notes"]
            before["text"] += "\n\n" + after["text"]
            before["may_continue"] = after["may_continue"]
            before["joined_from"] = after["entry_id"]
    entries = [entry for row in sorted(per_page) for entry in per_page[row]]
    for entry in entries:
        entry["chars"] = len(entry["text"])
    kinds = Counter(entry["kind"] for entry in entries)
    return {
        "stage": "extract.entries", "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": {"page_types": "dictionary pages split at capitalised headwords; article pages give one entry",
                   "entry_classes": sorted(ENTRY_CLASSES), "note_classes": sorted(NOTE_CLASSES),
                   "joins": "consecutive rows of one volume with consecutive printed page numbers "
                            "when titles or guide words agree"},
        "counts": {"entries": len(entries), "by_kind": dict(kinds),
                   "cross_references": sum(1 for entry in entries if entry["see"]),
                   "untitled": sum(1 for entry in entries if not entry["title"]),
                   "joined": sum(1 for join in joins if join["joined"]),
                   "page_types": dict(Counter(page["page_type"] for page in pages))},
        "joins": joins, "pages": pages, "entries": entries,
    }


def write_entries(out_dir: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Write entries.json next to the page records and return its counts."""
    result = build_entries(records)
    (Path(out_dir) / "entries.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return result["counts"]
