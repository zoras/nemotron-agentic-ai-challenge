"""The evaluate stage checks the review file; it does not judge the runs itself."""
import json

import pytest

from nemotron_challenge import evaluate


def case(case_id, classification, run_record="artifacts/agent/runs/q1.json", **extra):
    return {"case_id": case_id, "classification": classification, "title": "t", "run_record": run_record,
            "question": "q", "evidence": "e", "result": "r", "limits": "l", **extra}


@pytest.fixture
def repo(tmp_path):
    runs = tmp_path / "artifacts" / "agent" / "runs"
    runs.mkdir(parents=True)
    for name in ("q1", "q2"):
        (runs / f"{name}.json").write_text(json.dumps({"question_id": name, "hermes_version": "Hermes 9"}))
    return tmp_path


def write_review(repo, cases):
    path = repo / "evaluation" / "review.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"reviewer": "a team member", "cases": cases}))
    return path


def test_review_needs_three_cases_of_each_kind_with_existing_runs(repo):
    good = [case(f"S{n}", "success") for n in range(3)] + [case(f"F{n}", "failure") for n in range(3)]
    assert len(evaluate.read_review(write_review(repo, good), repo)) == 6
    with pytest.raises(ValueError, match="expected 3 failure cases, found 2"):
        evaluate.read_review(write_review(repo, good[:5]), repo)
    with pytest.raises(ValueError, match="does not exist"):
        evaluate.read_review(write_review(repo, good[:5] + [case("F2", "failure", "artifacts/agent/runs/nope.json")]), repo)
    with pytest.raises(ValueError, match="separate run record"):
        evaluate.read_review(write_review(repo, good[:5] + [case(
            "F2", "failure", repaired_by="artifacts/agent/runs/q1.json")]), repo)
    with pytest.raises(ValueError, match="missing limits"):
        evaluate.read_review(write_review(repo, good[:5] + [case("F2", "failure", limits=" ")]), repo)
    path = write_review(repo, good)
    path.write_text(json.dumps({"cases": good}))
    with pytest.raises(ValueError, match="missing reviewer"):
        evaluate.read_review(path, repo)


def test_stage_writes_cases_markdown_and_reproducibility(repo):
    write_review(repo, [case(f"S{n}", "success") for n in range(3)]
                 + [case("F0", "failure", repaired_by="artifacts/agent/runs/q2.json")]
                 + [case(f"F{n}", "failure") for n in (1, 2)])
    result = evaluate.run_evaluate(repo / "artifacts", repo)
    assert result["by_classification"] == {"success": 3, "failure": 3}
    cases = json.loads((repo / "artifacts" / "evaluate" / "cases.json").read_text())
    assert {"case_id", "classification", "title", "question", "result", "evidence", "run_record"} <= set(cases["cases"][0])
    markdown = (repo / "artifacts" / "evaluate" / "cases" / "F0.md").read_text()
    assert "Classification: failure" in markdown and "Repaired by: artifacts/agent/runs/q2.json" in markdown
    assert "Reviewer: a team member" in markdown and cases["reviewer"] == "a team member"
    record = json.loads((repo / "artifacts" / "evaluate" / "reproducibility.json").read_text())
    assert record["data"]["britannica"]["sample_size"] == 100 and record["models"]["embed"]["revision"]
    assert record["runtime"]["hermes"] == ["Hermes 9"] and len(record["agent_runs"]) == 2


def test_stage_without_a_review_still_records_reproducibility(tmp_path):
    result = evaluate.run_evaluate(tmp_path / "artifacts", tmp_path)
    assert "skipped" in result["cases"] and (tmp_path / "artifacts" / "evaluate" / "reproducibility.json").exists()


def test_calibration_sweeps_thresholds_and_compares_embedder_with_reranker():
    def row(page_id, title, logit, embed_rank, titled=False, navigation=False):
        return {"page_id": page_id, "title": title, "rerank_logit": logit, "embed_rank": embed_rank,
                "sources": ["title:x"] if titled else ["bm25:1:q"], "navigation": navigation}
    matches = {"results": [
        {"target_id": "a", "entry_id": "a", "target": "topic", "decision": "accepted", "ranked": [row("1", "Sword", 5.0, 2, True), row("2", "Katana", 1.0, 1)]},
        {"target_id": "b", "entry_id": "b", "target": "topic", "decision": "accepted", "ranked": [row("3", "Thorvaldsen", 0.5, 1, True)]},
        {"target_id": "c", "entry_id": "c", "target": "topic", "decision": "uncertain", "ranked": [row("9", "List", 8.0, 1, navigation=True), row("4", "Geysir", -1.0, 2)]},
    ]}
    labels = [{"target_id": "a", "page_id": "1", "correct": True}, {"target_id": "a", "page_id": "2", "correct": False},
              {"target_id": "b", "page_id": "3", "correct": False}, {"target_id": "c", "page_id": "4", "correct": False}]
    report = evaluate.calibration(matches, labels, {"a": "headword", "b": "headword", "c": "headword"})
    assert report["sweeps"]["topic/headword/title"] == [{"threshold": 0.5, "kept": 2, "precision": 0.5, "correct_dropped": 0},
                                               {"threshold": 5.0, "kept": 1, "precision": 1.0, "correct_dropped": 0}]
    assert report["sweeps"]["topic/headword/keyword"][0]["precision"] == 0.0
    versus = report["embedder_vs_reranker"]
    assert (versus["top1_differs"], versus["reranker_right_embedder_wrong"]) == (1, 1)
    assert report["by_decision"]["accepted"] == {"labelled": 2, "correct": 1}


def test_sweep_thresholds_never_exceed_the_scores_they_come_from():
    row = {"page_id": "1", "title": "A", "rerank_logit": 0.46, "embed_rank": 1, "sources": ["title:A"], "navigation": False}
    matches = {"results": [{"target_id": "a", "entry_id": "a", "target": "topic", "decision": "accepted", "ranked": [row]}]}
    report = evaluate.calibration(matches, [{"target_id": "a", "page_id": "1", "correct": True}], {"a": "headword"})
    assert report["sweeps"]["topic/headword/title"] == [{"threshold": 0.4, "kept": 1, "precision": 1.0, "correct_dropped": 0}]
