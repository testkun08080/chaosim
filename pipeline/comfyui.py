"""ComfyUI workflows as a subprocess (with an ffmpeg stub fallback).

The workflows live in a separate repository, ``comfyui-sandbox``, together with
their schema validator and the one place an API key is ever attached. We drive
its ``scripts/comfy_run.py`` as a subprocess, exactly like Blender in
``renderer.py`` and the HyperFrames CLI in ``hyperframes.py``. That keeps the
billing guard, the pre-flight validation and ``--dry-run`` on the sandbox side,
and keeps ``COMFY_API_KEY`` out of this repository entirely.

When the sandbox is not reachable (or ``CHAOSIM_STUB=1``), every call degrades
to an ffmpeg-generated placeholder so the rest of the pipeline still runs.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from pipeline.config import stub_mode
from pipeline.ffmpeg_utils import drawtext_font_prefix, escape_drawtext, run_ffmpeg

DEFAULT_SANDBOX = Path("../comfyui-sandbox")

# comfy_run.py exits non-zero when a workflow produces nothing, and its own
# polling can run long. Videos take minutes; keep the ceiling generous.
DEFAULT_TIMEOUT = 1800


def sandbox_root() -> Path:
    """Directory of the comfyui-sandbox checkout (override: COMFYUI_SANDBOX_PATH)."""
    custom = os.environ.get("COMFYUI_SANDBOX_PATH")
    root = Path(custom) if custom else DEFAULT_SANDBOX
    if not root.is_absolute():
        root = (Path.cwd() / root).resolve()
    return root


def workflow_path(name: str) -> Path:
    """Resolve ``08_video/keyframe_then_video.json`` to a file in the sandbox."""
    name = name if name.endswith(".json") else f"{name}.json"
    return sandbox_root() / "workflows_api" / name


def dry_run_mode() -> bool:
    """True when every ComfyUI call should be a costed-out dry run.

    A cost guard, not a stub: the workflow is still validated and priced, but
    nothing is sent and nothing is billed.
    """
    return os.environ.get("CHAOSIM_COMFY_DRY_RUN", "").lower() in ("1", "true", "yes")


def comfyui_available() -> bool:
    """True if the sandbox runner can be invoked (and stub mode is off)."""
    if stub_mode():
        return False
    runner = sandbox_root() / "scripts" / "comfy_run.py"
    return runner.is_file()


def get_comfy_cmd() -> list[str]:
    """Base command for invoking the sandbox runner.

    Prefers ``uv run`` (what the sandbox documents) and falls back to the
    interpreter running this pipeline, which already has ``requests``.
    """
    root = sandbox_root()
    runner = root / "scripts" / "comfy_run.py"
    if shutil.which("uv") and (root / "uv.lock").is_file():
        return ["uv", "run", "--project", str(root), str(runner)]
    return [sys.executable, str(runner)]


def _as_set_args(overrides: dict[str, object]) -> list[str]:
    """``{"10.duration": 5}`` -> ``["--set", "10.duration=5"]``.

    Every value goes through ``json.dumps``, strings included. comfy_run parses
    each value as JSON first and only falls back to a plain string, so an
    unquoted prompt that happens to read as JSON — a bare number, ``true``, or
    anything starting with a bracket — would otherwise arrive as the wrong type.
    Quoting it makes the round trip exact.
    """
    args: list[str] = []
    for key, value in overrides.items():
        args += ["--set", f"{key}={json.dumps(value, ensure_ascii=False)}"]
    return args


def run_workflow(workflow: str, overrides: dict[str, object], out_dir: Path,
                 dry_run: bool | None = None, timeout: int = DEFAULT_TIMEOUT) -> list[Path]:
    """Run one workflow and return the files it produced.

    Returns an empty list for a dry run — nothing was generated. Callers that
    need a file regardless (the render stage) fall back to a stub themselves.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dry_run = dry_run_mode() if dry_run is None else dry_run

    path = workflow_path(workflow)
    if not path.is_file():
        raise FileNotFoundError(
            f"workflow not found: {path}\n"
            f"Set COMFYUI_SANDBOX_PATH to a comfyui-sandbox checkout "
            f"(currently {sandbox_root()})."
        )

    cmd = get_comfy_cmd() + [
        str(path), "--out", str(out_dir.resolve()), "--json", "--timeout", str(timeout),
    ] + _as_set_args(overrides)
    if dry_run:
        cmd.append("--dry-run")

    print(f"  comfyui: {workflow}" + ("  (dry run)" if dry_run else ""))
    result = subprocess.run(cmd, cwd=sandbox_root(), capture_output=True, text=True,
                            timeout=timeout + 120)
    if result.returncode != 0:
        # comfy_run puts every human-readable line on stderr in --json mode.
        raise RuntimeError(
            f"ComfyUI workflow failed ({workflow}, exit {result.returncode}):\n"
            + (result.stderr or "").strip()[-4000:]
        )

    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise RuntimeError(
            f"ComfyUI runner returned no JSON for {workflow}: {result.stdout[-2000:]}"
        ) from exc

    return [Path(p) for p in payload.get("files", [])]


# --- stub fallback ---------------------------------------------------------

def stub_clip(out_path: Path, duration: float, label: str,
              width: int = 1080, height: int = 1920, fps: int = 30) -> Path:
    """Placeholder footage standing in for one generated shot."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = escape_drawtext(f"[COMFY STUB] {label}")
    run_ffmpeg([
        "-f", "lavfi", "-i", f"testsrc2=s={width}x{height}:r={fps}:d={duration}",
        "-vf", (
            "format=yuv420p,"
            f"drawtext={drawtext_font_prefix()}text='{text}':fontcolor=white:fontsize=44:"
            "x=(w-text_w)/2:y=120:shadowcolor=black:shadowx=2:shadowy=2"
        ),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(duration),
        str(out_path),
    ])
    return out_path


def stub_still(out_path: Path, label: str, width: int = 1080, height: int = 1920) -> Path:
    """Placeholder image standing in for one generated look asset."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = escape_drawtext(f"[COMFY STUB] {label}")
    run_ffmpeg([
        "-f", "lavfi", "-i", f"gradients=s={width}x{height}:d=0.1",
        "-frames:v", "1",
        "-vf", (
            f"drawtext={drawtext_font_prefix()}text='{text}':fontcolor=white:fontsize=40:"
            "x=(w-text_w)/2:y=(h-text_h)/2:shadowcolor=black:shadowx=2:shadowy=2"
        ),
        str(out_path),
    ])
    return out_path


def stub_tone(out_path: Path, duration: float, freq: int = 440) -> Path:
    """Placeholder one-shot standing in for a generated sound effect.

    A short decaying sine — enough for the mix to be audible and for the SFX
    report to measure timing without any sound library present.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.05, float(duration))
    run_ffmpeg([
        "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}:sample_rate=44100",
        "-af", f"afade=t=out:st=0:d={duration}",
        str(out_path),
    ])
    return out_path
