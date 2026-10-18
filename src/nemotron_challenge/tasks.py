"""Teams implement these stages with their coding agents."""
from pathlib import Path
from typing import Any

from .config import Settings

STAGES = ("extract", "match", "compare", "agent", "site", "evaluate")
IMPLEMENTED = {"extract", "match", "compare", "agent", "site", "evaluate"}


def extract(settings: Settings, work_dir: Path, scan_dir: Path = Path("data/raw/britannica")) -> dict[str, Any]:
    """Parse every sample scan: one full-page layout pass, then masked column crops at 3x. Replies are cached.
    Then split the pages into entries and join entries that continue onto the next scan."""
    from .clients import ParseClient
    from .data import load_manifest
    from .entries import write_entries
    from .extract import ParseRunner, extract_pages, write_extraction

    manifest = load_manifest()
    out_dir = Path(work_dir) / "extract"
    with ParseClient(settings.parse_base_url, settings.parse_api_key) as client:
        runner = ParseRunner(client, out_dir / "raw")
        records = extract_pages(runner, manifest["pages"], scan_dir)
    summary = write_extraction(out_dir, manifest, records, runner.requests_sent)
    entries = write_entries(out_dir, records)
    return {key: summary[key] for key in ("stage", "code_revision", "coverage")} | {
        "entries": entries, "output_dir": str(out_dir)}


def match(settings: Settings, work_dir: Path, scan_dir: Path = Path("data/raw/britannica")) -> dict[str, Any]:
    """Match each entry: Super VL proposes titles and queries, title lookup and BM25 give candidates,
    the embedder and reranker order them, and a rule decides. Replies and vectors are cached."""
    import httpx

    from .clients import ChatClient, RetrievalClient, WikiClient
    from .match import VectorCache, run_match

    with WikiClient(settings.wikipedia_api_url) as wiki, \
            RetrievalClient(settings.retrieval_base_url, settings.retrieval_api_key) as retrieval, \
            ChatClient(settings.super_base_url, settings.super_api_key, settings.super_model) as chat, \
            httpx.Client() as http:
        counts = run_match(Path(work_dir), scan_dir, wiki=wiki, retrieval=retrieval, chat=chat, http=http,
                           vectors=VectorCache(settings.db_path), cache_dir=Path("data/cache/match"))
    return {"stage": "match", "counts": counts, "output_dir": str(Path(work_dir) / "match")}


def compare(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Compare accepted matches: vocabulary overlap, distinctive words, a joint topic model over Nemotron
    embeddings, and Super VL fact checks with verified quotes. Replies and vectors are cached."""
    from .clients import ChatClient, RetrievalClient
    from .compare import run_compare
    from .facts import run_facts
    from .match import VectorCache

    vectors = VectorCache(settings.db_path)
    with RetrievalClient(settings.retrieval_base_url, settings.retrieval_api_key) as retrieval, \
            ChatClient(settings.super_base_url, settings.super_api_key, settings.super_model) as chat:
        counts = run_compare(Path(work_dir), vectors=vectors, retrieval=retrieval)
        facts = run_facts(Path(work_dir), vectors=vectors, retrieval=retrieval, chat=chat)
    return {"stage": "compare", "counts": counts, "facts": facts, "output_dir": str(Path(work_dir) / "compare")}


def agent(settings: Settings, work_dir: Path, hermes_home: Path = Path("data/hermes")) -> dict[str, Any]:
    """Build the agent index from saved artifacts, then ask Hermes the fixed question set when it is installed."""
    from .agent import QUESTIONS, build_index, find_hermes, run_question, sync_plugin

    counts = build_index(Path(work_dir))
    if find_hermes() is None:
        return {"stage": "agent", "index": counts, "runs": "skipped: the hermes CLI is not installed (docs/hermes.md)"}
    sync_plugin(hermes_home)
    runs = [run_question(question, Path(work_dir) / "agent" / "runs", hermes_home) for question in QUESTIONS]
    return {"stage": "agent", "index": counts, "runs": [
        {**{k: run[k] for k in ("question_id", "exit_code", "elapsed_s", "model")},
         "tool_calls": [call["name"] for call in run["tool_calls"]]} for run in runs]}


def site(settings: Settings, work_dir: Path, site_dir: Path = Path("site"),
         scan_dir: Path = Path("data/raw/britannica")) -> dict[str, Any]:
    """Compile one LaTeX source document per scan and build the static website around them."""
    from .site import run_site

    return {"stage": "site", "build": run_site(Path(work_dir), site_dir, scan_dir), "output_dir": str(site_dir)}


def evaluate(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Write the reviewed agent case studies and the reproducibility record."""
    from .evaluate import run_evaluate

    return {"stage": "evaluate", **run_evaluate(Path(work_dir)), "output_dir": str(Path(work_dir) / "evaluate")}
