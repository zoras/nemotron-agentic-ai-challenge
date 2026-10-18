"""Run Parse 3.5 on the Britannica scans. Raw replies stay apart from derived records."""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import statistics
import threading
import time
from typing import Any

from PIL import Image, ImageDraw, ImageStat

from .clients import ParseClient, ServiceError
from .config import DEFAULT_PARSE_PROMPT, PARSE_MODEL

BLOCK = re.compile(r"<x_([0-9.]+)><y_([0-9.]+)>(.*?)<x_([0-9.]+)><y_([0-9.]+)><class_([A-Za-z_-]+)>", re.S)
RETRY_STATUS = {429, 502, 503, 504}
MAX_ATTEMPTS = 4
DEFAULT_MAX_TOKENS = 8744
BODY_CLASSES = {"Text", "List-item", "Section-header", "Footnote", "Title"}
INK_DROP = 70              # a pixel is ink when it is this much darker than the page median
BLANK_INK = 0.002          # pages below this ink fraction carry no print
PLATE_TEXT_CHARS = 1500    # pages with pictures and less body text than this are plates
WIDE_BLOCK = 0.6           # a block wider than this spans both columns
GUTTER_BANDS = 12          # trace the column gap in this many horizontal bands
GUTTER_SEARCH = 0.06       # search this far either side of the gap that the layout blocks suggest
GUTTER_OUTLIER = 0.03      # replace a band position this far from the median gap
SPAN_PAD = 0.004           # widen full-width spans so that no text line is cut
MIN_SEGMENT = 0.03         # two-column segments shorter than this join the full-width segment
HEAD_SCALE = 3
HEAD_CANVAS = 0.5          # Parse reads a lone head line best at the top of a blank page this tall (share of width)
COLUMN_SCALE = 3
TILE_SCALE = 2
MAX_SPLITS = 2


def parse_blocks(content: str) -> list[dict[str, Any]]:
    """Split Parse markup into blocks in model reading order. Boxes are relative to the input image."""
    blocks = []
    for order, match in enumerate(BLOCK.finditer(content)):
        x0, y0, text, x1, y1, label = match.groups()
        blocks.append({"order": order, "class": label, "text": text.strip(),
                       "bbox": [float(x0), float(y0), float(x1), float(y1)]})
    return blocks


def unmatched_text(content: str) -> str:
    """Return reply text outside complete block markup, such as a cut-off final block."""
    return BLOCK.sub("", content).strip()


def request_key(image: bytes, prompt: str, max_tokens: int) -> str:
    material = json.dumps({"model": PARSE_MODEL, "image_sha256": hashlib.sha256(image).hexdigest(),
                           "prompt": prompt, "max_tokens": max_tokens}, sort_keys=True)
    return hashlib.sha256(material.encode()).hexdigest()


class ParseRunner:
    """Send one image per request, cache each reply by request key, and log failures."""

    def __init__(self, client: ParseClient, raw_dir: Path, *, prompt: str = DEFAULT_PARSE_PROMPT):
        self.client, self.raw_dir, self.prompt = client, Path(raw_dir), prompt
        self._log_lock, self._verify_lock = threading.Lock(), threading.Lock()
        self.requests_sent = 0

    def run(self, page_stem: str, label: str, image: bytes, mime: str, meta: dict[str, Any],
            max_tokens: int = DEFAULT_MAX_TOKENS) -> dict[str, Any]:
        path = self.raw_dir / page_stem / f"{label}.json"
        key = request_key(image, self.prompt, max_tokens)
        if path.is_file():
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached["request"]["key"] == key:
                return cached
            old = path.parent / "superseded" / f"{label}.{cached['request']['key'][:12]}.json"
            old.parent.mkdir(exist_ok=True)
            path.replace(old)  # keep the earlier reply as evidence; a changed request never overwrites it
        with self._verify_lock:
            if not getattr(self.client, "_verified", True):
                self.client.verify_model()  # check the catalog once, and only when a request is needed
            self.requests_sent += 1
        request = {"key": key, "model": PARSE_MODEL, "prompt": self.prompt, "max_tokens": max_tokens,
                   "image_sha256": hashlib.sha256(image).hexdigest(), "image_bytes": len(image),
                   "mime": mime, **meta}
        payload = {
            "model": PARSE_MODEL, "max_tokens": max_tokens, "stream": False, "temperature": 0,
            "skip_special_tokens": False, "add_special_tokens": False,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": self.prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(image).decode()}"}},
            ]}],
        }
        started, attempts, reply, error = time.monotonic(), 0, None, None
        while attempts < MAX_ATTEMPTS:
            attempts += 1
            try:
                reply = self.client.request("POST", "chat/completions", payload=payload)
                break
            except ServiceError as exc:
                error = {"type": type(exc).__name__, "message": str(exc), "status_code": exc.status_code}
                retryable = exc.status_code is None or exc.status_code in RETRY_STATUS
                if not retryable or attempts == MAX_ATTEMPTS:
                    break
                delay = float(exc.retry_after) if (exc.retry_after or "").isdigit() else 2.0 ** attempts
                time.sleep(min(delay, 30.0))
        if reply is None:
            self._log_failure(page_stem, label, request, error, attempts)
            raise ServiceError(f"Parse failed for {page_stem}/{label}: {error}")
        choice = (reply.get("choices") or [{}])[0]
        record = {
            "request": request,
            "response_model": reply.get("model"),
            "finish_reason": choice.get("finish_reason"),
            "usage": reply.get("usage"),
            "attempts": attempts,
            "elapsed_s": round(time.monotonic() - started, 2),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "content": (choice.get("message") or {}).get("content") or "",
            "reply": reply,
        }
        if record["response_model"] != PARSE_MODEL:
            self._log_failure(page_stem, label, request, {"type": "ModelMismatch", "message": record["response_model"]}, attempts)
            raise ServiceError(f"Parse reply model differs for {page_stem}/{label}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
        return record

    def _log_failure(self, page_stem: str, label: str, request: dict[str, Any], error: Any, attempts: int) -> None:
        entry = {"page": page_stem, "label": label, "request_key": request["key"], "error": error,
                 "attempts": attempts, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        with self._log_lock:
            self.raw_dir.mkdir(parents=True, exist_ok=True)
            with (self.raw_dir / "failures.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry) + "\n")


def scan_mime(filename: str) -> str:
    return {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[filename.rsplit(".", 1)[1]]


def read_scan(scan_dir: Path, page: dict[str, Any]) -> bytes:
    image = (Path(scan_dir) / page["filename"]).read_bytes()
    if hashlib.sha256(image).hexdigest() != page["image_sha256"]:
        raise ValueError(f"scan checksum differs for {page['page_id']}; run `nemotron-challenge data fetch`")
    return image


def ink_mask(image: Image.Image) -> tuple[Image.Image, int]:
    """Return a 0/255 mask of printed pixels and the page median grey level."""
    gray = image.convert("L")
    histogram = gray.histogram()
    half, seen, median = gray.width * gray.height / 2, 0, 0
    for median, count in enumerate(histogram):
        seen += count
        if seen >= half:
            break
    threshold = median - INK_DROP
    return gray.point(lambda value: 255 if value < threshold else 0), median


def ink_fraction(mask: Image.Image, box: tuple[int, int, int, int] | None = None) -> float:
    region = mask.crop(box) if box else mask
    return region.resize((1, 1), Image.BOX).getpixel((0, 0)) / 255


def classify_page(image: Image.Image, layout_blocks: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """Label a scan as cover, blank, plate, or text from its ink and the layout pass."""
    mask, median = ink_mask(image)
    ink = ink_fraction(mask)
    body_chars = sum(len(block["text"]) for block in layout_blocks if block["class"] in BODY_CLASSES)
    pictures = sum(1 for block in layout_blocks if block["class"] == "Picture")
    evidence = {"ink_fraction": round(ink, 5), "median_grey": median, "layout_body_chars": body_chars,
                "layout_pictures": pictures}
    if ink < BLANK_INK:
        return ("cover" if median < 150 else "blank"), evidence
    if pictures and body_chars < PLATE_TEXT_CHARS:
        return "plate", evidence
    return "text", evidence


def is_running_head(block: dict[str, Any]) -> bool:
    """Running heads sit on one line at the top. Parse sometimes labels them Section-header or Title."""
    x0, y0, x1, y1 = block["bbox"]
    if block["class"] == "Page-header":
        return y0 < 0.12
    return block["class"] in {"Section-header", "Title"} and y1 < 0.1 and y1 - y0 < 0.04 and x1 - x0 > 0.4


def body_top(layout_blocks: list[dict[str, Any]]) -> float:
    """Return the lower edge of the running head, or 0 when the layout pass found none."""
    heads = [block["bbox"][3] for block in layout_blocks if is_running_head(block)]
    return round(min(max(heads) + 0.003, 0.15), 4) if heads else 0.0


def head_top(layout_blocks: list[dict[str, Any]]) -> float:
    """Return the upper edge of the running head, or 0. Column crops start here, so no body line is cut."""
    heads = [block["bbox"][1] for block in layout_blocks if is_running_head(block)]
    return round(max(min(heads) - 0.005, 0.0), 4) if heads else 0.0


def wide_spans(layout_blocks: list[dict[str, Any]], top: float) -> list[list[float]]:
    """Return merged vertical spans of blocks that cross both columns, such as tables and footnotes."""
    spans = []
    for block in layout_blocks:
        x0, y0, x1, y1 = block["bbox"]
        if block["class"] in {"Page-header", "Page-footer"} or is_running_head(block) or x1 - x0 <= WIDE_BLOCK:
            continue
        if y1 <= y0 or y1 - y0 > 0.5 or y1 <= top:
            continue  # the layout pass returned an implausible box; do not plan around it
        spans.append([max(y0 - SPAN_PAD, top), min(y1 + SPAN_PAD, 1.0)])
    merged: list[list[float]] = []
    for span in sorted(spans):
        if merged and span[0] <= merged[-1][1] + 0.01:
            merged[-1][1] = max(merged[-1][1], span[1])
        else:
            merged.append(span)
    return [[round(y0, 4), round(y1, 4)] for y0, y1 in merged]


def gutter_guess(layout_blocks: list[dict[str, Any]], y_top: float = 0.0, y_bottom: float = 1.0) -> float | None:
    """Estimate the column gap from layout blocks whose centre lies between y_top and y_bottom."""
    body = [block["bbox"] for block in layout_blocks
            if block["class"] in {"Text", "List-item"} and 0.2 < block["bbox"][2] - block["bbox"][0] <= WIDE_BLOCK
            and y_top <= (block["bbox"][1] + block["bbox"][3]) / 2 <= y_bottom]
    left = [box[2] for box in body if (box[0] + box[2]) / 2 < 0.5]
    right = [box[0] for box in body if (box[0] + box[2]) / 2 >= 0.5]
    return (max(left) + min(right)) / 2 if left and right else None


def find_gutter(image: Image.Image, guess: float, y_top: float, y_bottom: float) -> list[list[float]]:
    """Trace the gap between two text columns band by band, so that slight skew does not matter.

    Return [[y0, y1, x], ...] in page coordinates.
    """
    mask, _ = ink_mask(image)
    x0, x1 = int(image.width * (guess - GUTTER_SEARCH)), int(image.width * (guess + GUTTER_SEARCH))
    target = guess * image.width - x0
    count = max(1, round(GUTTER_BANDS * (y_bottom - y_top)))
    step, bands = (y_bottom - y_top) / count, []
    for index in range(count):
        y0, y1 = y_top + index * step, y_top + (index + 1) * step
        box = (x0, int(y0 * image.height), x1, max(int(y1 * image.height), int(y0 * image.height) + 1))
        profile = list(mask.crop(box).resize((x1 - x0, 1), Image.BOX).getdata())
        best = min(range(len(profile)), key=lambda j: (profile[j], abs(j - target)))
        bands.append([round(y0, 4), round(y1, 4), round((x0 + best) / image.width, 4)])
    middle = statistics.median(band[2] for band in bands)
    for band in bands:
        if abs(band[2] - middle) > GUTTER_OUTLIER:
            band[2] = round(middle, 4)
    return bands


def split_crop(image: Image.Image, crop: list[float]) -> tuple[list[float], list[float]]:
    """Split a crop into upper and lower parts at the whitest text row near its middle."""
    mask, _ = ink_mask(image)
    left, right = int(crop[0] * image.width), int(crop[2] * image.width)
    y0 = int((crop[1] + 0.4 * (crop[3] - crop[1])) * image.height)
    y1 = int((crop[1] + 0.6 * (crop[3] - crop[1])) * image.height)
    profile = list(mask.crop((left, y0, right, y1)).resize((1, y1 - y0), Image.BOX).getdata())
    cut = round((y0 + min(range(len(profile)), key=profile.__getitem__)) / image.height, 4)
    return [crop[0], crop[1], crop[2], cut], [crop[0], cut, crop[2], crop[3]]


def plan_regions(image: Image.Image, layout_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cut the page into horizontal segments: two masked column crops between full-width blocks."""
    top, head_bottom = head_top(layout_blocks), body_top(layout_blocks)
    page_guess = gutter_guess(layout_blocks)
    segments, cursor = [], top
    for y0, y1 in wide_spans(layout_blocks, head_bottom):
        if y0 - cursor > MIN_SEGMENT:
            segments.append(("columns", cursor, y0))
        segments.append(("wide", max(y0, cursor), y1))
        cursor = max(cursor, y1)
    if 1.0 - cursor > MIN_SEGMENT or not segments:
        segments.append(("columns", cursor, 1.0))
    else:
        kind, y0, _ = segments.pop()
        segments.append((kind, y0, 1.0))
    regions = []
    for index, (kind, y0, y1) in enumerate(segments):
        guess = (gutter_guess(layout_blocks, y0, y1) or page_guess) if kind == "columns" else None
        if guess is not None:
            bands = find_gutter(image, guess, y0, y1)
            xs = [band[2] for band in bands]
            regions += [{"label": f"s{index}-col-left", "crop": [0.0, y0, round(min(max(xs) + 0.005, 1.0), 4), y1],
                         "scale": COLUMN_SCALE, "keep": "left", "gutter": bands},
                        {"label": f"s{index}-col-right", "crop": [round(max(min(xs) - 0.005, 0.0), 4), y0, 1.0, y1],
                         "scale": COLUMN_SCALE, "keep": "right", "gutter": bands}]
        elif y1 - y0 > 0.45:
            upper, lower = split_crop(image, [0.0, y0, 1.0, y1])
            regions += [{"label": f"s{index}-wide.a", "crop": upper, "scale": TILE_SCALE},
                        {"label": f"s{index}-wide.b", "crop": lower, "scale": TILE_SCALE}]
        else:
            regions.append({"label": f"s{index}-wide", "crop": [0.0, y0, 1.0, y1], "scale": TILE_SCALE})
    if head_bottom > 0:
        regions.insert(0, {"label": "head", "crop": [0.0, top, 1.0, head_bottom], "scale": HEAD_SCALE, "canvas": HEAD_CANVAS})
    return [{**region, "crop": [round(value, 4) for value in region["crop"]]} for region in regions]


def crop_png(image: Image.Image, region: dict[str, Any]) -> bytes:
    """Crop and upscale a region. For a column, paint the other column with the paper colour first."""
    page = image.convert("RGB")
    if region.get("keep"):
        page = page.copy()
        paper = tuple(int(value) for value in ImageStat.Stat(page).median)
        draw = ImageDraw.Draw(page)
        for y0, y1, x in region["gutter"]:
            top, bottom, cut = int(y0 * page.height), int(y1 * page.height) + 1, int(x * page.width)
            if region["keep"] == "left":
                draw.rectangle([cut + 1, top, page.width, bottom], fill=paper)
            else:
                draw.rectangle([0, top, cut - 1, bottom], fill=paper)
    crop, scale = region["crop"], region["scale"]
    box = (round(crop[0] * page.width), round(crop[1] * page.height), round(crop[2] * page.width), round(crop[3] * page.height))
    cut_out = page.crop(box)
    cut_out = cut_out.resize((cut_out.width * scale, cut_out.height * scale), Image.LANCZOS)
    if region.get("canvas"):
        paper = tuple(int(value) for value in ImageStat.Stat(page).median)
        canvas = Image.new("RGB", (cut_out.width, max(int(cut_out.width * region["canvas"]), cut_out.height)), paper)
        canvas.paste(cut_out, (0, int(cut_out.width * 0.02)))
        cut_out = canvas
    buffer = io.BytesIO()
    cut_out.save(buffer, format="PNG")
    return buffer.getvalue()


def to_page_box(bbox: list[float], crop: list[float]) -> list[float]:
    """Map a box relative to a crop back to page-relative coordinates."""
    width, height = crop[2] - crop[0], crop[3] - crop[1]
    return [round(crop[0] + bbox[0] * width, 4), round(crop[1] + bbox[1] * height, 4),
            round(crop[0] + bbox[2] * width, 4), round(crop[1] + bbox[3] * height, 4)]


def parse_region(runner: ParseRunner, page: dict[str, Any], image: Image.Image, region: dict[str, Any],
                 depth: int = 0) -> list[dict[str, Any]]:
    """Parse one region. Split it and retry when the reply stops at the token limit."""
    stem = Path(page["filename"]).stem
    meta = {"page_id": page["page_id"], "variant": region["label"], "crop": region["crop"], "scale": region["scale"],
            "keep": region.get("keep"), "gutter": region.get("gutter"), "canvas": region.get("canvas")}
    record = runner.run(stem, region["label"], crop_png(image, region), "image/png", meta)
    attempt = {**region, "raw_path": f"{stem}/{region['label']}.json", "finish_reason": record["finish_reason"],
               "request_key": record["request"]["key"], "record": record}
    if record["finish_reason"] == "stop" or depth >= MAX_SPLITS:
        return [attempt]
    upper, lower = split_crop(image, region["crop"])
    parts = [{**region, "label": f"{region['label']}.{suffix}", "crop": crop}
             for suffix, crop in (("a", upper), ("b", lower))]
    return [{**attempt, "superseded": True}] + [result for part in parts
                                                 for result in parse_region(runner, page, image, part, depth + 1)]


def clean_head(text: str) -> str:
    """Reduce a head-strip reply to its first printed line. Parse returns letter-spaced heads as one-row tables."""
    text = re.sub(r"\\begin\{tabular\}\{[^}]*\}|\\end\{tabular\}|\\mbox\{\}", "", text)
    text = re.sub(r"\\multicolumn\{\d+\}\{[^}]*\}\{([^}]*)\}", r"\1", text)
    text = text.replace("\\\\", "\n").replace("&", " ").replace("**", "").replace("_", "")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return next((line for line in lines if line), "")


def label_margin_notes(blocks: list[dict[str, Any]], region: str) -> None:
    """Mark narrow blocks outside the column's body text span as margin notes."""
    body = [block for block in blocks if block["class"] == "Text" and block["bbox"][2] - block["bbox"][0] > 0.25]
    if len(body) < 2:
        return
    left = statistics.median(block["bbox"][0] for block in body)
    right = statistics.median(block["bbox"][2] for block in body)
    for block in blocks:
        x0, _, x1, _ = block["bbox"]
        outside = x1 <= left + 0.01 if region.endswith("col-left") or "col-left." in region else x0 >= right - 0.01
        short = block["class"] in {"Text", "Section-header", "List-item", "Title", "Caption"} or (
            block["class"] == "Picture" and 0 < len(block["text"]) < 80)
        if x1 - x0 < 0.15 and outside and short:
            block["parse_class"], block["class"] = block["class"], "Margin-note"


def page_record(page: dict[str, Any], status: str, evidence: dict[str, Any], layout: dict[str, Any],
                attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the derived page record.

    Text pages take the running head from the 3x head strip (the layout pass is the fallback) and the
    body from the column and full-width regions. Plates keep the layout blocks. Covers and blank pages
    keep no blocks, because Parse invents text for them.
    """
    stem = Path(page["filename"]).stem
    layout_blocks = parse_blocks(layout["content"])
    head_bottom = body_top(layout_blocks)
    blocks = [{**block, "source": "layout"} for block in layout_blocks] if status == "plate" else []
    regions, head_blocks = [], []
    for attempt in attempts:
        record = attempt.pop("record")
        regions.append(dict(attempt))
        if record is None or attempt.get("superseded"):
            continue
        label, region_blocks = attempt["label"], parse_blocks(record["content"])
        if not attempt.get("canvas"):
            for block in region_blocks:
                block["bbox"] = to_page_box(block["bbox"], attempt["crop"])
        if label == "head":
            text = clean_head(" ".join(block["text"] for block in region_blocks))
            if text:
                head_blocks = [{"class": "Page-header", "parse_class": ",".join(block["class"] for block in region_blocks),
                                "text": text, "bbox": attempt["crop"], "source": label}]
            continue
        if "col-" in label:
            label_margin_notes(region_blocks, label)
        for block in region_blocks:
            if (block["bbox"][1] + block["bbox"][3]) / 2 < head_bottom and len(block["text"]) < 60:
                block["parse_class"], block["class"] = block["class"], "Head-fragment"
        blocks += [{**block, "source": label} for block in region_blocks]
        leftover = unmatched_text(record["content"])
        if leftover:
            blocks.append({"class": "Unstructured", "text": leftover, "bbox": attempt["crop"], "source": label})
    if status == "text":
        if not head_blocks:
            head_blocks = [{**block, "class": "Page-header", "parse_class": block["class"], "source": "layout"}
                           for block in layout_blocks if is_running_head(block)]
        blocks = sorted(head_blocks, key=lambda block: block["bbox"][0]) + blocks
    for order, block in enumerate(blocks):
        block["order"] = order
        block["id"] = f"{stem}:b{order}"
    unfinished = [region["label"] for region in regions
                  if region["finish_reason"] != "stop" and not region.get("superseded") and not region.get("skipped")]
    if status == "text" and unfinished:
        status = "partial"
    return {
        "page_id": page["page_id"], "row_index": page["row_index"], "volume_id": page["volume_id"],
        "filename": page["filename"], "image_sha256": page["image_sha256"],
        "status": status, "status_evidence": evidence,
        "running_head": " | ".join(block["text"] for block in blocks if block["class"] == "Page-header"),
        "layout_raw": f"{stem}/layout.json", "layout_finish_reason": layout["finish_reason"],
        "regions": regions, "unfinished_regions": unfinished, "blocks": blocks,
    }


def extract_page(runner: ParseRunner, page: dict[str, Any], scan_dir: Path) -> dict[str, Any]:
    """Run the layout pass and, for text pages, the region pass for one scan."""
    raw = read_scan(scan_dir, page)
    stem = Path(page["filename"]).stem
    layout = runner.run(stem, "layout", raw, scan_mime(page["filename"]),
                        {"page_id": page["page_id"], "variant": "full_page", "crop": [0.0, 0.0, 1.0, 1.0], "scale": 1})
    image = Image.open(io.BytesIO(raw))
    layout_blocks = parse_blocks(layout["content"])
    status, evidence = classify_page(image, layout_blocks)
    attempts = []
    if status == "text":
        mask, _ = ink_mask(image)
        for region in plan_regions(image, layout_blocks):
            crop = region["crop"]
            box = (int(crop[0] * image.width), int(crop[1] * image.height), int(crop[2] * image.width), int(crop[3] * image.height))
            if ink_fraction(mask, box) < BLANK_INK:
                attempts.append({**region, "skipped": "no ink", "finish_reason": "skipped", "record": None})
                continue
            attempts += parse_region(runner, page, image, region)
    return page_record(page, status, evidence, layout, attempts)


def extract_pages(runner: ParseRunner, pages: list[dict[str, Any]], scan_dir: Path,
                  workers: int = 2) -> list[dict[str, Any]]:
    """Extract every page. A failed page returns a record with status `failed` and the error."""
    def one(page: dict[str, Any]) -> dict[str, Any]:
        try:
            return extract_page(runner, page, scan_dir)
        except (ServiceError, ValueError, OSError) as exc:
            return {"page_id": page["page_id"], "row_index": page["row_index"], "volume_id": page["volume_id"],
                    "filename": page["filename"], "image_sha256": page["image_sha256"], "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}", "blocks": []}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, pages))


def code_revision() -> str:
    """Return the git commit of the working tree, marked when uncommitted changes exist."""
    import subprocess

    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{commit}+dirty" if dirty else commit


def write_extraction(out_dir: Path, manifest: dict[str, Any], records: list[dict[str, Any]],
                     requests_sent: int) -> dict[str, Any]:
    """Write one derived record per page and a coverage summary. Return the summary."""
    pages_dir = Path(out_dir) / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    rows, by_status = [], {}
    for record in records:
        (pages_dir / f"{Path(record['filename']).stem}.json").write_text(
            json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
        body = [block for block in record["blocks"] if block["class"] not in {"Page-header", "Page-footer", "Margin-note"}]
        by_status[record["status"]] = by_status.get(record["status"], 0) + 1
        rows.append({"page_id": record["page_id"], "filename": record["filename"], "status": record["status"],
                     "running_head": record.get("running_head", ""), "blocks": len(record["blocks"]),
                     "body_chars": sum(len(block["text"]) for block in body),
                     "margin_notes": sum(1 for block in record["blocks"] if block["class"] == "Margin-note"),
                     "regions": [region["label"] for region in record.get("regions", []) if not region.get("superseded")],
                     "unfinished_regions": record.get("unfinished_regions", []), "error": record.get("error")})
    regions = [region for record in records for region in record.get("regions", [])]
    summary = {
        "stage": "extract", "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_revision": code_revision(), "parse_model": PARSE_MODEL, "parse_prompt": DEFAULT_PARSE_PROMPT,
        "dataset": manifest["dataset"], "dataset_revision": manifest["revision"],
        "manifest_sha256": manifest["manifest_sha256"],
        "method": {"layout_pass": "full page at source resolution",
                   "region_pass": "masked two-column crops between full-width blocks, otherwise full-width tiles",
                   "column_scale": COLUMN_SCALE, "tile_scale": TILE_SCALE, "split_on_length": MAX_SPLITS},
        "coverage": {"pages": len(records), "by_status": by_status, "region_replies": len(regions),
                     "superseded_regions": sum(1 for region in regions if region.get("superseded")),
                     "unfinished_regions": sum(len(record.get("unfinished_regions", [])) for record in records),
                     "parse_requests_this_run": requests_sent},
        "pages": rows,
    }
    (Path(out_dir) / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    return summary
