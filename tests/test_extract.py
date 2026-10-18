"""Extraction mechanics with synthetic inputs. These tests do not measure OCR accuracy."""
import io
import json

from PIL import Image, ImageDraw
import pytest

from nemotron_challenge.clients import ServiceError
from nemotron_challenge.config import PARSE_MODEL
from nemotron_challenge import extract


def two_columns(skew: float = 0.0, width: int = 600, height: int = 800) -> Image.Image:
    """Draw text-like rows in two columns. The gap between them drifts by `skew` pixels per row."""
    image = Image.new("RGB", (width, height), (225, 215, 195))
    draw = ImageDraw.Draw(image)
    for y in range(60, height - 20, 12):
        shift = int(skew * y)
        draw.rectangle([30 + shift, y, 280 + shift, y + 6], fill=(40, 30, 20))
        draw.rectangle([310 + shift, y, 570 + shift, y + 6], fill=(40, 30, 20))
    return image


def reply(content: str, finish: str = "stop") -> dict:
    return {"model": PARSE_MODEL, "usage": {"completion_tokens": 1},
            "choices": [{"finish_reason": finish, "message": {"content": content}}]}


class FakeClient:
    _verified = True

    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def request(self, method, path, *, payload=None, params=None):
        self.calls += 1
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_parse_markup_keeps_order_class_and_boxes():
    content = ("<x_0.1><y_0.02>FARM.<x_0.5><y_0.04><class_Page-header>\n\n"
               "<x_0.05><y_0.1>The country was cleared.<x_0.45><y_0.4><class_Text>\n\n<x_0.0><y_0.0>cut off")
    blocks = extract.parse_blocks(content)
    assert [(block["order"], block["class"], block["text"]) for block in blocks] == [
        (0, "Page-header", "FARM."), (1, "Text", "The country was cleared.")]
    assert blocks[1]["bbox"] == [0.05, 0.1, 0.45, 0.4]
    assert extract.unmatched_text(content) == "<x_0.0><y_0.0>cut off"


def test_crop_boxes_map_back_to_page_coordinates():
    assert extract.to_page_box([0.0, 0.0, 1.0, 1.0], [0.5, 0.1, 1.0, 0.9]) == [0.5, 0.1, 1.0, 0.9]
    assert extract.to_page_box([0.5, 0.5, 1.0, 1.0], [0.5, 0.1, 1.0, 0.9]) == [0.75, 0.5, 1.0, 0.9]


@pytest.mark.parametrize("image,expected", [
    (Image.new("RGB", (600, 800), (120, 90, 60)), "cover"),
    (Image.new("RGB", (600, 800), (230, 225, 210)), "blank"),
    (two_columns(), "text"),
])
def test_page_classes_come_from_ink_not_from_parse_text(image, expected):
    invented = [{"class": "Text", "text": "We have used this method to evaluate the results.", "bbox": [0, 0, 1, 1]}]
    status, evidence = extract.classify_page(image, invented if expected != "text" else [])
    assert status == expected
    assert 0 <= evidence["ink_fraction"] <= 1


def test_plate_needs_pictures_and_little_body_text():
    picture = [{"class": "Picture", "text": "", "bbox": [0.1, 0.1, 0.9, 0.9]}]
    assert extract.classify_page(two_columns(), picture)[0] == "plate"


@pytest.mark.parametrize("skew", [0.0, 0.02])
def test_gutter_trace_stays_in_the_gap_on_skewed_pages(skew):
    image = two_columns(skew)
    bands = extract.find_gutter(image, 0.49, 0.05, 1.0)
    for y0, y1, x in bands:
        shift = skew * ((y0 + y1) / 2) * image.height
        assert (280 + shift) / image.width <= x <= (310 + shift) / image.width


def test_full_width_footnote_gets_its_own_region():
    layout = [
        {"class": "Page-header", "text": "FAR", "bbox": [0.2, 0.02, 0.7, 0.05]},
        {"class": "Text", "text": "left", "bbox": [0.05, 0.07, 0.47, 0.8]},
        {"class": "Text", "text": "right", "bbox": [0.52, 0.07, 0.95, 0.8]},
        {"class": "Footnote", "text": "(a) note", "bbox": [0.05, 0.82, 0.95, 0.9]},
    ]
    regions = extract.plan_regions(two_columns(), layout)
    assert [region["label"] for region in regions] == [
        "head", "s0-col-left", "s0-col-right", "s1-wide", "s2-col-left", "s2-col-right"]
    assert regions[0]["crop"] == [0.0, 0.015, 1.0, 0.053] and regions[0]["scale"] == 3
    assert regions[1]["crop"][1] == 0.015  # columns start at the head top, so no body line is cut
    assert regions[3]["crop"][1] < 0.82 and regions[3]["crop"][3] > 0.9
    assert regions[1]["keep"] == "left" and regions[2]["keep"] == "right"


def test_column_crop_paints_out_the_other_column():
    image = two_columns()
    bands = [[0.0, 1.0, 0.49]]
    left = Image.open(io.BytesIO(extract.crop_png(
        image, {"crop": [0.0, 0.0, 0.6, 1.0], "scale": 1, "keep": "left", "gutter": bands})))
    assert left.size == (360, 800)
    assert min(left.convert("L").crop((300, 0, 360, 800)).getdata()) > 150


def test_runner_caches_replies_and_keeps_length_stops(tmp_path):
    client = FakeClient([reply("<x_0><y_0>a<x_1><y_1><class_Text>", finish="length")])
    runner = extract.ParseRunner(client, tmp_path)
    first = runner.run("page-0001", "layout", b"image", "image/png", {"page_id": "p1"})
    second = runner.run("page-0001", "layout", b"image", "image/png", {"page_id": "p1"})
    assert client.calls == 1 and runner.requests_sent == 1
    assert first["finish_reason"] == "length" and second == first
    saved = json.loads((tmp_path / "page-0001" / "layout.json").read_text())
    assert saved["request"]["page_id"] == "p1" and saved["reply"]["model"] == PARSE_MODEL


def test_runner_logs_a_rejected_request_and_does_not_retry_it(tmp_path):
    client = FakeClient([ServiceError("service returned HTTP 422", status_code=422)])
    runner = extract.ParseRunner(client, tmp_path)
    with pytest.raises(ServiceError):
        runner.run("page-0001", "layout", b"image", "image/png", {})
    assert client.calls == 1
    entry = json.loads((tmp_path / "failures.jsonl").read_text().splitlines()[0])
    assert entry["error"]["status_code"] == 422


def test_runner_retries_a_busy_service(tmp_path, monkeypatch):
    monkeypatch.setattr(extract.time, "sleep", lambda seconds: None)
    client = FakeClient([ServiceError("busy", status_code=429, retry_after="1"), reply("ok")])
    record = extract.ParseRunner(client, tmp_path).run("page-0001", "layout", b"image", "image/png", {})
    assert client.calls == 2 and record["attempts"] == 2


def test_region_that_stops_at_the_token_limit_is_split(tmp_path):
    client = FakeClient([reply("<x_0><y_0>part<x_1><y_0.5><class_Text>", "length"),
                         reply("<x_0><y_0>upper<x_1><y_1><class_Text>"), reply("<x_0><y_0>lower<x_1><y_1><class_Text>")])
    runner = extract.ParseRunner(client, tmp_path)
    page = {"filename": "page-0001-abc.jpg", "page_id": "p1"}
    region = {"label": "s0-wide", "crop": [0.0, 0.0, 1.0, 1.0], "scale": 1}
    attempts = extract.parse_region(runner, page, two_columns(), region)
    assert [(a["label"], a.get("superseded", False)) for a in attempts] == [
        ("s0-wide", True), ("s0-wide.a", False), ("s0-wide.b", False)]
    assert attempts[1]["crop"][3] == attempts[2]["crop"][1]


def test_changed_request_moves_the_earlier_reply_aside(tmp_path):
    client = FakeClient([reply("first"), reply("second")])
    runner = extract.ParseRunner(client, tmp_path)
    first = runner.run("page-0001", "s0-col-left", b"crop-v1", "image/png", {})
    runner.run("page-0001", "s0-col-left", b"crop-v2", "image/png", {})
    kept = list((tmp_path / "page-0001" / "superseded").glob("s0-col-left.*.json"))
    assert len(kept) == 1 and json.loads(kept[0].read_text())["request"]["key"] == first["request"]["key"]


@pytest.mark.parametrize("reply_text,expected", [
    ("\\begin{tabular}{ccc}\n & O & P & T & I & C & S. & 427\\\\\n\\end{tabular}", "O P T I C S. 427"),
    ("POLITICAL ECONOMY. Chap. II.\nNature of Wealth, The fecond fort", "POLITICAL ECONOMY. Chap. II."),
    ("**FAR [ 107 ] FAR**", "FAR [ 107 ] FAR"),
    ("A S T & \\multicolumn{2}{c}{[ 852 ]} & \\mbox{} & A S T", "A S T [ 852 ] A S T"),
])
def test_head_strip_reply_is_reduced_to_its_first_line(reply_text, expected):
    assert extract.clean_head(reply_text) == expected
