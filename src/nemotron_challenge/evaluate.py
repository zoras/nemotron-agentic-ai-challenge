"""Write the agent case studies and the reproducibility record.

Whether a run is a success or a failure is a reviewer's judgement. The reviewer records it, with the
evidence, in evaluation/review.json. This stage checks the review against the saved runs, then writes
artifacts/evaluate/cases.json, one case study per case from templates/case-study.md, and
artifacts/evaluate/reproducibility.json with the code revision, models, data revisions, and limits.
"""
from __future__ import annotations

from datetime import datetime, timezone
from importlib import metadata
import json
import math
from pathlib import Path
import platform
import subprocess
from typing import Any

from .config import (EMBED_MODEL, EMBED_REVISION, PARSE_MODEL, RERANK_MODEL, RERANK_REVISION, SUPER_MODEL,
                     WIKIPEDIA_REVISION)

CASE_FIELDS = ("case_id", "classification", "title", "run_record", "question", "evidence", "result", "limits")
CLASSIFICATIONS = {"success": 3, "failure": 3}
PACKAGES = ("httpx", "lancedb", "numpy", "pillow", "pyarrow", "scikit-learn", "umap-learn", "wordfreq", "matplotlib")


def read_review(path: Path, repo: Path) -> list[dict[str, Any]]:
    """Return the reviewed cases. Raise ValueError when the review is incomplete or names a missing run."""
    review = json.loads(path.read_text(encoding="utf-8"))
    cases = review["cases"]
    problems = [] if str(review.get("reviewer") or "").strip() else ["missing reviewer: who judged the runs"]
    for case in cases:
        missing = [field for field in CASE_FIELDS if not str(case.get(field) or "").strip()]
        if missing:
            problems.append(f"{case.get('case_id')}: missing {', '.join(missing)}")
        if case.get("classification") not in CLASSIFICATIONS:
            problems.append(f"{case.get('case_id')}: classification must be success or failure")
        if case.get("run_record") and not (repo / case["run_record"]).exists():
            problems.append(f"{case.get('case_id')}: run record {case['run_record']} does not exist")
        repaired = case.get("repaired_by")
        if repaired and repaired == case.get("run_record"):
            problems.append(f"{case.get('case_id')}: a repaired result must be a separate run record")
    ids = [case.get("case_id") for case in cases]
    if len(set(ids)) != len(ids):
        problems.append("case IDs repeat")
    for classification, count in CLASSIFICATIONS.items():
        found = sum(1 for case in cases if case.get("classification") == classification)
        if found != count:
            problems.append(f"expected {count} {classification} cases, found {found}")
    if problems:
        raise ValueError("evaluation review: " + "; ".join(problems))
    return cases


def case_markdown(case: dict[str, Any], revision: str, reviewer: str) -> str:
    repair = f"\nRepaired by: {case['repaired_by']}" if case.get("repaired_by") else ""
    return (f"# Case study\n\nCase ID: {case['case_id']}\nClassification: {case['classification']}\n"
            f"Run record: {case['run_record']}{repair}\nCode revision: {revision}\nReviewer: {reviewer}\n\n"
            f"## Question\n\n{case['question']}\n\n## Evidence\n\n{case['evidence']}\n\n"
            f"## Result\n\n{case['result']}\n\n### Limits\n\n{case['limits']}\n")


def calibration(matches: dict[str, Any], labels: list[dict[str, Any]], entry_kinds: dict[str, str]) -> dict[str, Any]:
    """Measure the match rules against hand-labelled candidates.

    A label says whether a candidate article covers the target's subject. Reranker scores differ in scale by
    query: a continuation topic is queried with Super VL's modern description, a headword topic with the OCR
    text. So the report sweeps thresholds per group (target and entry kind), separately for candidates
    reached through a proposed title and candidates found only by keyword search. It also compares the
    embedder's first choice with the reranker's."""
    correct = {(row["target_id"], str(row["page_id"])): bool(row["correct"]) for row in labels}
    best_rows, disagreements = [], []
    for result in matches["results"]:
        eligible = [row for row in result["ranked"] if not row["navigation"]]
        if not eligible:
            continue
        best, embed_best = eligible[0], min(eligible, key=lambda row: row["embed_rank"])
        margin = best["rerank_logit"] - eligible[1]["rerank_logit"] if len(eligible) > 1 else None
        best_rows.append({"target_id": result["target_id"], "decision": result["decision"], "logit": best["rerank_logit"],
                          "margin": margin, "group": f"{result['target']}/{entry_kinds[result['entry_id']]}",
                          "titled": any(s.startswith("title:") for s in best["sources"]),
                          "correct": correct.get((result["target_id"], best["page_id"]))})
        if embed_best["page_id"] != best["page_id"]:
            disagreements.append({"target_id": result["target_id"], "reranker": best["title"], "embedder": embed_best["title"],
                                  "reranker_correct": correct.get((result["target_id"], best["page_id"])),
                                  "embedder_correct": correct.get((result["target_id"], embed_best["page_id"]))})

    def sweep(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        labelled = [row for row in rows if row["correct"] is not None]
        out = []
        for threshold in sorted({math.floor(row["logit"] * 10) / 10 for row in labelled}):
            kept = [row for row in labelled if row["logit"] >= threshold]
            out.append({"threshold": threshold, "kept": len(kept), "precision": round(sum(r["correct"] for r in kept) / len(kept), 3),
                        "correct_dropped": sum(1 for r in labelled if r["correct"] and r["logit"] < threshold)})
        return out

    labelled = [row for row in best_rows if row["correct"] is not None]
    judged = [row for row in disagreements if row["reranker_correct"] is not None and row["embedder_correct"] is not None]
    return {
        "labelled_targets": len(labelled), "targets": len(best_rows),
        "by_decision": {decision: {"labelled": sum(1 for r in labelled if r["decision"] == decision),
                                   "correct": sum(1 for r in labelled if r["decision"] == decision and r["correct"])}
                        for decision in ("accepted", "uncertain", "no_match")},
        "sweeps": {f"{group}/{'title' if titled else 'keyword'}": sweep(rows) for (group, titled), rows in sorted(
            ((key, [row for row in best_rows if (row["group"], row["titled"]) == key])
             for key in {(row["group"], row["titled"]) for row in best_rows}), key=lambda item: item[0]) if rows},
        "labelled_rows": [row for row in best_rows if row["correct"] is not None],
        "embedder_vs_reranker": {
            "targets": len(best_rows), "top1_differs": len(disagreements), "both_labelled": len(judged),
            "reranker_right_embedder_wrong": sum(1 for r in judged if r["reranker_correct"] and not r["embedder_correct"]),
            "embedder_right_reranker_wrong": sum(1 for r in judged if r["embedder_correct"] and not r["reranker_correct"]),
            "both_right": sum(1 for r in judged if r["reranker_correct"] and r["embedder_correct"]),
            "both_wrong": sum(1 for r in judged if not r["reranker_correct"] and not r["embedder_correct"]),
            "examples": disagreements},
    }


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    return completed.stdout.strip() if completed.returncode == 0 else ""


def reproducibility(repo: Path, work_dir: Path) -> dict[str, Any]:
    from .data import load_manifest

    manifest = load_manifest()
    versions = {}
    for package in PACKAGES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    deployment_path = repo / "infra" / "nebius" / "deployment.json"
    matches_path = work_dir / "match" / "matches.json"
    matches = json.loads(matches_path.read_text(encoding="utf-8")) if matches_path.exists() else {}
    runs = sorted(str(path.relative_to(repo)) for path in (work_dir / "agent" / "runs").glob("*.json")) \
        if (work_dir / "agent" / "runs").exists() else []
    hermes = sorted({run.get("hermes_version") for run in (json.loads((repo / path).read_text(encoding="utf-8"))
                                                          for path in runs) if run.get("hermes_version")})
    return {
        "code": {"revision": git(repo, "rev-parse", "HEAD"), "uncommitted_changes": bool(git(repo, "status", "--porcelain"))},
        "runtime": {"python": platform.python_version(), "platform": platform.platform(), "packages": versions,
                    "hermes": hermes},
        "models": {"parse": PARSE_MODEL, "embed": {"model": EMBED_MODEL, "revision": EMBED_REVISION},
                   "rerank": {"model": RERANK_MODEL, "revision": RERANK_REVISION}, "super": SUPER_MODEL},
        "data": {"britannica": {k: manifest.get(k) for k in ("dataset", "revision", "source_file", "source_file_sha256",
                                                             "manifest_sha256", "sample_size")},
                 "wikipedia_snapshot_revision": WIKIPEDIA_REVISION},
        "serving": json.loads(deployment_path.read_text(encoding="utf-8")) if deployment_path.exists() else None,
        "match_method": matches.get("method"),
        "agent_runs": runs,
    }


def run_evaluate(work_dir: Path, repo: Path = Path("."), review_path: Path | None = None) -> dict[str, Any]:
    work_dir, repo = Path(work_dir), Path(repo)
    review_path = review_path or repo / "evaluation" / "review.json"
    out = work_dir / "evaluate"
    out.mkdir(parents=True, exist_ok=True)
    record = reproducibility(repo, work_dir)
    record["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (out / "reproducibility.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    labels_path, matches_path = repo / "evaluation" / "match_labels.json", work_dir / "match" / "matches.json"
    if labels_path.exists() and matches_path.exists():
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
        kinds = {entry["entry_id"]: entry["kind"] for entry in
                 json.loads((work_dir / "extract" / "entries.json").read_text(encoding="utf-8"))["entries"]}
        report = {"labeller": labels["labeller"], "method": labels["method"],
                  "thresholds": json.loads(matches_path.read_text(encoding="utf-8"))["method"].get("thresholds"),
                  **calibration(json.loads(matches_path.read_text(encoding="utf-8")), labels["labels"], kinds)}
        (out / "match_calibration.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    if not review_path.exists():
        return {"reproducibility": str(out / "reproducibility.json"), "cases": f"skipped: {review_path} does not exist"}
    cases = read_review(review_path, repo)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    revision = record["code"]["revision"] + (" (with uncommitted changes)" if record["code"]["uncommitted_changes"] else "")
    (out / "cases").mkdir(exist_ok=True)
    for case in cases:
        (out / "cases" / f"{case['case_id']}.md").write_text(case_markdown(case, revision, review["reviewer"]),
                                                             encoding="utf-8")
    (out / "cases.json").write_text(json.dumps({"code_revision": revision, "reviewer": review["reviewer"],
                                                "ground_truth_scans": review.get("ground_truth_scans"), "cases": cases},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    return {"reproducibility": str(out / "reproducibility.json"), "cases": len(cases),
            "by_classification": {c: sum(1 for case in cases if case["classification"] == c) for c in CLASSIFICATIONS}}
