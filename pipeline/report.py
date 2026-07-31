"""Data-file output for the concept checks.

The judging views under ``docs/`` are written for humans. These helpers write the
same information as data files under ``outputs/`` so it can be diffed, loaded from
a script, or opened in a spreadsheet. ``outputs/`` is gitignored, so in CI these
files reach you as workflow artifacts rather than as commits.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = REPO_ROOT / "outputs"


def write_json(path: Path, data) -> Path:
    """Write UTF-8 JSON, matching how runner.py/renderer.py write their sidecars."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> Path:
    """Write a flat table.

    Encoded as utf-8-**sig**: concept titles are Japanese, and Excel misreads
    plain UTF-8 CSV without the BOM. Every other file in this repo is plain
    utf-8 — this one is the deliberate exception.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path
