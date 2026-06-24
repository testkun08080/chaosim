"""Blender render orchestration (with an ffmpeg placeholder fallback)."""

import os
import shutil
import subprocess
from pathlib import Path

from pipeline.config import stub_mode
from pipeline.ffmpeg_utils import drawtext_font_prefix, escape_drawtext, run_ffmpeg


def get_blender_path() -> str:
    return os.environ.get("BLENDER_PATH", "blender")


def blender_available() -> bool:
    """True if Blender can be invoked (and stub mode is off)."""
    if stub_mode():
        return False
    blender = get_blender_path()
    return shutil.which(blender) is not None or os.path.isfile(blender)


def render_concept(concept: dict, concept_path: Path, output_dir: Path,
                   preset: str | None = None) -> Path:
    """Run Blender headlessly to render a concept. Returns output video path.

    Falls back to an ffmpeg-generated placeholder clip when Blender is not
    installed (or CHAOSIM_STUB=1), so the rest of the pipeline stays testable.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = concept.get("slug", "render")
    output_path = output_dir / f"{slug}.mp4"

    if not blender_available():
        return _stub_render(concept, output_path)

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


def _stub_render(concept: dict, output_path: Path) -> Path:
    """Placeholder simulation footage: animated test pattern + label."""
    duration = min(int(concept.get("duration_sec", 10) or 10), 30)
    label = escape_drawtext(f"[SIM STUB] {concept.get('scene_script', 'simulation')}")
    vf = (
        "format=yuv420p,"
        f"drawtext={drawtext_font_prefix()}text='{label}':fontcolor=white:fontsize=46:"
        "x=(w-text_w)/2:y=80:shadowcolor=black:shadowx=2:shadowy=2"
    )
    run_ffmpeg([
        "-f", "lavfi", "-i", f"testsrc2=s=1080x1920:r=60:d={duration}",
        "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(duration),
        str(output_path),
    ])
    return output_path
