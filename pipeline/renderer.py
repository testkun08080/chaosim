"""Blender render orchestration."""

import subprocess
import os
from pathlib import Path
import yaml


def get_blender_path() -> str:
    return os.environ.get("BLENDER_PATH", "blender")


def render_concept(concept: dict, concept_path: Path, output_dir: Path, preset: str | None = None) -> Path:
    """Run Blender headlessly to render a concept. Returns output video path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = concept.get("slug", "render")
    output_path = output_dir / f"{slug}.mp4"

    blender = get_blender_path()
    runner = Path(__file__).parent.parent / "simulators" / "blender" / "runner.py"

    cmd = [
        blender,
        "--background",
        "--python", str(runner),
        "--",
        str(concept_path.resolve()),
        str(output_path.resolve()),
        preset or concept.get("render_preset", "medium"),
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Blender render failed with code {result.returncode}")

    return output_path
