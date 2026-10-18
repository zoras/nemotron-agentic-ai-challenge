"""Teams implement these stages with their coding agents."""
from pathlib import Path
from typing import Any

from .config import Settings

STAGES = ("extract", "match", "compare", "agent", "site", "evaluate")
IMPLEMENTED = {"extract"}


def _unfinished(stage: str) -> None:
    raise NotImplementedError(
        f"TODO: implement the {stage} milestone. Read docs/milestones.md#{stage}. "
        "The starter has no result for this stage."
    )


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


def match(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """TODO: define how your team finds and verifies article matches."""
    _unfinished("match")


def compare(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """TODO: define your vocabulary, frequency, or topic comparison."""
    _unfinished("compare")


def agent(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """TODO: implement your Hermes tools and evidence checks."""
    _unfinished("agent")


def site(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """TODO: build your LaTeX documents and static website."""
    _unfinished("site")


def evaluate(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """TODO: review your results and document successes and failures."""
    _unfinished("evaluate")
