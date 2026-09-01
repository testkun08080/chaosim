"""Render orchestration: pick a backend, produce footage + an events sidecar.

``concept["source"]`` selects the backend:

* ``blender`` (default) — physics simulation, the original path.
* ``comfyui``           — footage generated from prompts (``comfyui_render``).
* ``hybrid``            — ComfyUI makes the look assets, Blender still simulates.

All three end at the same two files, ``outputs/renders/<slug>.mp4`` and
``<slug>_events.json``, so nothing downstream branches on the backend.
"""

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

from pipeline.config import stub_mode
from pipeline.ffmpeg_utils import drawtext_font_prefix, escape_drawtext, run_ffmpeg

_MAC_BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"


def get_blender_path() -> str:
    """Resolve Blender binary from env, PATH, or common macOS install location."""
    custom = os.environ.get("BLENDER_PATH")
    if custom:
        return custom
    which = shutil.which("blender")
    if which:
        return which
    if platform.system() == "Darwin" and os.path.isfile(_MAC_BLENDER):
        return _MAC_BLENDER
    return "blender"


def blender_available() -> bool:
    """True if Blender can be invoked (and stub mode is off)."""
    if stub_mode():
        return False
    blender = get_blender_path()
    return shutil.which(blender) is not None or os.path.isfile(blender)


SOURCES = ("blender", "comfyui", "hybrid")


def concept_source(concept: dict) -> str:
    """Which render backend a concept asks for. Unknown values fail loudly."""
    source = str(concept.get("source") or "blender").lower()
    if source not in SOURCES:
        raise ValueError(
            f"unknown source {source!r} in concept "
            f"{concept.get('slug', '?')} (choose from: {', '.join(SOURCES)})"
        )
    return source


def render_concept(concept: dict, concept_path: Path, output_dir: Path,
                   preset: str | None = None, dry_run: bool = False) -> Path:
    """Render a concept with its declared backend. Returns the output video path.

    Falls back to an ffmpeg-generated placeholder clip when the backend's tool
    is not installed (or CHAOSIM_STUB=1), so the rest of the pipeline stays
    testable.

    Branding stills (``params.still`` / ``duration_sec <= 0``) write a PNG
    instead of an MP4.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    source = concept_source(concept)
    if source != "blender":
        # Imported here so the Blender path never pays for the ComfyUI stack.
        from pipeline import comfyui_render
        if source == "comfyui":
            return comfyui_render.render_via_comfyui(concept, output_dir, dry_run=dry_run)
        concept = comfyui_render.apply_look_assets(concept, dry_run=dry_run)

    slug = concept.get("slug", "render")
    params = concept.get("params") or {}
    still = bool(params.get("still")) or float(concept.get("duration_sec") or 0) <= 0
    output_path = output_dir / (f"{slug}.png" if still else f"{slug}.mp4")

    if not blender_available():
        print("Blender not available — writing ffmpeg stub footage")
        if still:
            return _stub_still(concept, output_path)
        return _stub_render(concept, output_path)

    blender = get_blender_path()
    runner = Path(__file__).parent.parent / "simulators" / "blender" / "runner.py"

    # Pass JSON so Blender's bundled Python does not need PyYAML installed.
    concept_json = output_dir / f"{slug}_concept.json"
    concept_json.write_text(json.dumps(concept, ensure_ascii=False, indent=2), encoding="utf-8")

    cmd = [
        blender,
        "--background",
        "--python", str(runner),
        "--",
        str(concept_json.resolve()),
        str(output_path.resolve()),
        preset or concept.get("render_preset", "medium"),
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Blender render failed with code {result.returncode}")
    if not output_path.exists():
        raise RuntimeError(f"Blender finished but output missing: {output_path}")

    return output_path


def _stub_still(concept: dict, output_path: Path) -> Path:
    """Minimal PNG placeholder when Blender is unavailable."""
    title = escape_drawtext(concept.get("title", "Chaosim"))
    params = concept.get("params") or {}
    res = params.get("resolution") or concept.get("resolution") or [1080, 1080]
    w, h = int(res[0]), int(res[1])
    font = drawtext_font_prefix()
    run_ffmpeg([
        "-f", "lavfi", "-i", f"color=c=0x1a1a2e:s={w}x{h}:d=0.1",
        "-frames:v", "1",
        "-vf", (
            f"drawtext={font}text='{title}':fontsize=48:fontcolor=white:"
            "x=(w-text_w)/2:y=(h-text_h)/2"
        ),
        str(output_path),
    ])
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
