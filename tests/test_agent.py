"""Agent index and Hermes plugin tools on a tiny saved project. No model calls."""
import importlib.util
import json
from pathlib import Path

from nemotron_challenge import agent, compare

PLUGIN = Path(__file__).resolve().parents[1] / "integrations" / "hermes" / "nemotron-challenge" / "__init__.py"


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def tiny_project(root: Path) -> Path:
    work = root / "artifacts"
    entry = {"entry_id": "page-0251-abc:e8", "kind": "headword", "title": "SYDENHAM", "page_type": "dictionary",
             "text": "SYDENHAM (Dr Thomas), an excellent English phyfician, was born in 1624.",
             "margin_notes": [], "parts": [{"page_id": "britannica:r:train:251", "filename": "page-0251-abc.jpg",
                                            "image_sha256": "f" * 64, "row_index": 251, "block_ids": ["page-0251-abc:b17"]}]}
    write(work / "extract" / "entries.json", {"entries": [entry]})
    write(work / "extract" / "pages" / "page-0251-abc.json",
          {"blocks": [{"id": "page-0251-abc:b17", "bbox": [0.5, 0.66, 0.93, 0.93]}]})
    ranked = [{"page_id": "564669", "title": "Thomas Sydenham", "revision_id": "1341167433", "url": "u",
               "text_sha256": "a" * 64}, {"page_id": "1", "title": "Sydenham", "revision_id": "2", "url": "v", "text_sha256": "b" * 64}]
    write(work / "match" / "matches.json", {
        "plans": {"page-0251-abc:e8": {"topic": "Thomas Sydenham"}}, "counts": {"targets": 1}, "repeated_selections": {},
        "results": [{"entry_id": "page-0251-abc:e8", "target_id": "page-0251-abc:e8#topic", "target": "topic",
                     "label": "Thomas Sydenham", "decision": "accepted", "reason": "logit 5", "title": "Thomas Sydenham",
                     "page_id": "564669", "rerank_logit": 5.0, "margin": 3.0, "title_support": True, "ranked": ranked}]})
    write(work / "match" / "articles" / "564669.json", {
        "page_id": "564669", "title": "Thomas Sydenham", "url": "u", "revision_id": "1341167433", "text_sha256": "a" * 64,
        "text": "Thomas Sydenham was an English physician.\nHe was born in 1624 at Wynford Eagle in Dorset, and became known as the English Hippocrates."})
    write(work / "compare" / "comparison.json", {
        "counts": {"pairs": 1}, "text_changes": [], "topics": {},
        "distinctive_words": {"content_words": {"left": [{"word": "phyfick"}], "right": [{"word": "population"}]}},
        "pairs": [{"target_id": "page-0251-abc:e8#topic", "title": "Thomas Sydenham", "entry_coverage": 0.5,
                   "baseline_coverage": 0.1, "lift": 5.0, "shared_words": ["english"], "entry_only_words": [],
                   "entry_unknown_rate": 0.0}]})
    return work


def test_readable_text_folds_long_s_and_keeps_case():
    assert compare.readable("**Fuch** was the CAFE of the firft phyfician.") == "Such was the CAFE of the first physician."


def test_index_joins_source_match_and_vocabulary(tmp_path, monkeypatch):
    work = tiny_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    counts = agent.build_index(Path("artifacts"))
    index = json.loads((work / "agent" / "index.json").read_text())
    entry = index["entries"]["page-0251-abc:e8"]
    assert counts == {"entries": 1, "articles": 1, "entries_with_facts": 0}
    assert entry["source"][0]["bbox"] == [0.5, 0.66, 0.93, 0.93] and "physician" in entry["text_normalised"]
    assert entry["match"]["topic"]["revision_id"] == "1341167433" and entry["match"]["topic"]["runner_up"] == "Sydenham"
    assert index["articles"]["564669"]["path"] == "artifacts/match/articles/564669.json"


def load_plugin():
    spec = importlib.util.spec_from_file_location("nemotron_challenge_plugin", PLUGIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_plugin_tools_answer_from_the_index_and_report_missing_evidence(tmp_path, monkeypatch):
    tiny_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    agent.build_index(Path("artifacts"))
    monkeypatch.setenv("NEMOTRON_CHALLENGE_REPO", str(tmp_path))
    plugin = load_plugin()
    tools = {schema["name"]: plugin.guarded(handler) for schema, handler in plugin.TOOLS}
    found = json.loads(tools["challenge_search"]({"query": "Sydenham physician"}))
    assert found["results"][0]["entry_id"] == "page-0251-abc:e8"
    assert json.loads(tools["challenge_search"]({"query": "volcano"}))["results"] == []
    compared = json.loads(tools["challenge_compare"]({"entry_id": "page-0251-abc:e8"}))
    assert compared["match"]["topic"]["title"] == "Thomas Sydenham" and compared["vocabulary"]["lift"] == 5.0
    assert "error" in json.loads(tools["challenge_compare"]({"entry_id": "nope"}))
    passages = json.loads(tools["challenge_passages"]({"page_id": "564669", "query": "born Dorset"}))
    assert passages["passages"][0]["text"].startswith("He was born") and passages["passages"][0]["offset"] == 42
    scan = json.loads(tools["challenge_scan"]({"entry_id": "page-0251-abc:e8"}))
    assert scan["scans"][0]["image_path"].endswith("data/raw/britannica/page-0251-abc.jpg")


def test_plugin_registers_every_declared_tool():
    plugin = load_plugin()
    registered = []

    class Context:
        def register_tool(self, **kwargs):
            registered.append(kwargs["name"])
            assert kwargs["toolset"] == "nemotron_challenge" and kwargs["schema"]["name"] == kwargs["name"]

    plugin.register(Context())
    manifest = (PLUGIN.parent / "plugin.yaml").read_text()
    assert registered and all(f"  - {name}" in manifest for name in registered)


def test_stream_json_events_give_the_model_tool_calls_and_answer():
    from pathlib import Path
    stdout = Path("runs/hermes-smoke-20261018T151924Z.jsonl").read_text() if Path(
        "runs/hermes-smoke-20261018T151924Z.jsonl").exists() else "\n".join(json.dumps(e) for e in [
            {"type": "system", "subtype": "init", "model": "nvidia/Nemotron-3.5-Super-VL", "session_id": "s1"},
            {"type": "tool_use", "name": "challenge_corpus", "input": {}},
            {"type": "tool_result", "name": "challenge_corpus", "output": "{\"error\": \"x\"}", "is_error": True},
            {"type": "result", "text": "It returned an error.", "session_id": "s1"}])
    parsed = agent.read_events(stdout + "\nnot json")
    assert parsed["model"] == "nvidia/Nemotron-3.5-Super-VL"
    assert [call["name"] for call in parsed["tool_calls"]] == ["challenge_corpus"]
    assert parsed["tool_calls"][0]["is_error"] is True and parsed["answer"]


def test_index_writes_an_enlarged_entry_crop_for_the_scan_tool(tmp_path, monkeypatch):
    from PIL import Image

    tiny_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "raw" / "britannica").mkdir(parents=True)
    Image.new("RGB", (600, 800), "white").save(tmp_path / "data" / "raw" / "britannica" / "page-0251-abc.jpg")
    agent.build_index(Path("artifacts"))
    part = json.loads((tmp_path / "artifacts" / "agent" / "index.json").read_text())["entries"]["page-0251-abc:e8"]["source"][0]
    x1, y1, x2, y2 = part["region_px"]
    assert part["crop_scale"] == agent.CROP_SCALE
    assert Image.open(part["crop_path"]).size == ((x2 - x1) * 4, (y2 - y1) * 4)
    monkeypatch.setenv("NEMOTRON_CHALLENGE_REPO", str(tmp_path))
    scan = json.loads(load_plugin().guarded(load_plugin().scan)({"entry_id": "page-0251-abc:e8"}))["scans"][0]
    assert scan["crop_exists"] and scan["crop_path"] == str(tmp_path / part["crop_path"])


def test_long_crops_are_enlarged_less(tmp_path):
    from PIL import Image

    Image.new("RGB", (300, 1200), "white").save(tmp_path / "page.jpg")
    scale = agent.write_crop(tmp_path / "page.jpg", [0, 0, 300, 1200], tmp_path / "crop.png")
    assert scale == 2.0 and Image.open(tmp_path / "crop.png").size == (600, 2400)


def test_scan_regions_are_padded_pixel_boxes_inside_the_page():
    assert agent.pixel_region([0.1, 0.2, 0.5, 0.995], (1000, 2000)) == [90, 380, 510, 2000]
    assert agent.pixel_region(None, (1000, 2000)) is None and agent.pixel_region([0, 0, 1, 1], None) is None
