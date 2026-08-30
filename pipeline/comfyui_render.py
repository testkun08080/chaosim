"""The ComfyUI render stage: recipes -> clips -> ``<slug>.mp4`` + events sidecar.

The whole point of this module is that it produces exactly the two files the
Blender path produces — ``outputs/renders/<slug>.mp4`` and
``outputs/renders/<slug>_events.json``. Everything downstream (material,
narration, compose, thumbnail, upload) is untouched, because the stage contract
was never "Blender ran", it was "these two files exist"
(``docs/media-pipeline-playbook.md`` ch.1).

Two shapes:

* ``source: comfyui`` — every shot is generated; ``render_via_comfyui``.
* ``source: hybrid``  — only look assets are generated and the concept's params
  are repointed at them; ``apply_look_assets``, after which the Blender path
  runs as usual.
"""

from __future__ import annotations

import importlib
import shutil
from pathlib import Path

from pipeline import comfyui
from pipeline.compositor import concat_segments
from pipeline.config import load_settings
from pipeline.ffmpeg_utils import get_duration
from pipeline.sfx_events import cue_sheet_events, detect_onsets, snap_to_onsets, write_events
from simulators.comfyui import AVAILABLE_RECIPES, resolve_overrides

RECIPE_PACKAGE = "simulators.comfyui.recipes"

# Which produced file is the one we want. ComfyUI hands back everything the
# workflow saved, including the keyframe PNG next to the clip.
VIDEO_SUFFIXES = (".mp4", ".webm", ".mkv", ".mov")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def load_recipe(name: str):
    """Import a recipe module by name, the way runner.py loads a scene script."""
    if name not in AVAILABLE_RECIPES:
        raise ValueError(
            f"unknown ComfyUI recipe {name!r}. Register it in simulators/comfyui/__init__.py "
            f"(known: {', '.join(AVAILABLE_RECIPES)})"
        )
    return importlib.import_module(f"{RECIPE_PACKAGE}.{name}")


def recipe_name(concept: dict) -> str:
    return str((concept.get("comfyui") or {}).get("recipe") or "generative_shots")


def _pick(files: list[Path], suffixes: tuple[str, ...]) -> Path | None:
    for path in files:
        if path.suffix.lower() in suffixes:
            return path
    return None


def estimate(concept: dict) -> dict:
    """What a render would cost, without sending anything.

    Printed by ``render --dry-run``. The per-second figures are ComfyUI's own
    published rates for Wan Image-to-Video; anything else is left uncosted
    rather than guessed at.
    """
    module = load_recipe(recipe_name(concept))
    jobs = module.build_jobs(concept, concept.get("params") or {}, load_settings())
    per_second = {"480P": 0.05, "720P": 0.10, "1080P": 0.15}
    seconds = 0.0
    usd = 0.0
    for job in jobs:
        duration = float(job.get("duration") or 0)
        seconds += duration
        rate = per_second.get(str(job["inputs"].get("resolution") or ""))
        if rate:
            usd += rate * duration
    return {"jobs": len(jobs), "seconds": round(seconds, 1), "usd": round(usd, 2)}


def print_estimate(concept: dict) -> dict:
    est = estimate(concept)
    print(f"  jobs={est['jobs']}  footage={est['seconds']}s  "
          f"video cost ~${est['usd']} (image/audio nodes not included)")
    return est


# --- source: comfyui -------------------------------------------------------

def render_via_comfyui(concept: dict, output_dir: Path, dry_run: bool | None = None) -> Path:
    """Generate every shot, concatenate them, and write the events sidecar."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = concept.get("slug", "render")
    out_path = output_dir / f"{slug}.mp4"

    module = load_recipe(recipe_name(concept))
    jobs = module.build_jobs(concept, concept.get("params") or {}, load_settings())
    if not jobs:
        raise ValueError(
            f"{slug}: source is comfyui but no shots are declared "
            f"(concept.comfyui.shots is empty)"
        )

    dry_run = comfyui.dry_run_mode() if dry_run is None else dry_run
    available = comfyui.comfyui_available()
    if not available:
        print("ComfyUI sandbox not available — writing ffmpeg stub footage")
    print_estimate(concept)

    shots_dir = output_dir / f"{slug}_shots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    clips: list[Path] = []
    rendered: list[dict] = []
    for job in jobs:
        name = job["name"]
        clip = shots_dir / f"{name}.mp4"
        if available and not dry_run:
            files = comfyui.run_workflow(
                job["workflow"], resolve_overrides(job["workflow"], job["inputs"]), shots_dir,
            )
            produced = _pick(files, VIDEO_SUFFIXES)
            if produced is None:
                raise RuntimeError(
                    f"{slug}/{name}: {job['workflow']} produced no video "
                    f"(got: {[f.name for f in files] or 'nothing'})"
                )
            if produced != clip:
                shutil.move(str(produced), clip)
        else:
            comfyui.stub_clip(clip, job["duration"], f"{slug} {name}")
        # The model can return a slightly different length than we asked for;
        # the cue sheet must be laid out on what actually exists, not on the ask.
        actual = get_duration(clip) or float(job["duration"])
        clips.append(clip)
        rendered.append({"name": name, "duration": actual, "cues": job.get("cues") or []})
        print(f"  shot: {name} -> {clip} ({actual:.2f}s)")

    concat_segments(clips, out_path)
    write_shot_events(concept, rendered, out_path, output_dir)
    return out_path


def write_shot_events(concept: dict, shots: list[dict], video: Path, output_dir: Path) -> Path:
    """Build ``<slug>_events.json`` from the cue sheet, snapped to measured onsets."""
    slug = concept.get("slug", "render")
    cues = cue_sheet_events(shots)
    onsets = detect_onsets(video) if video.is_file() else []
    events = snap_to_onsets(cues, onsets)
    snapped = sum(1 for e in events if e.get("source") == "onset")
    print(f"  events: {len(events)} ({snapped} snapped to onsets, "
          f"{len(onsets)} onsets detected)")
    return write_events(
        output_dir / f"{slug}_events.json", events,
        meta={"slug": slug, "backend": "comfyui", "onsets_detected": len(onsets)},
    )


# --- source: hybrid --------------------------------------------------------

def apply_look_assets(concept: dict, dry_run: bool | None = None) -> dict:
    """Generate the concept's look assets and return a concept pointing at them.

    Falls back to stub images when the sandbox is unavailable, so a hybrid
    concept still renders (with a placeholder backplate) under ``CHAOSIM_STUB=1``.
    """
    module = load_recipe(recipe_name(concept))
    jobs = module.build_jobs(concept, concept.get("params") or {}, load_settings())
    if not jobs:
        return concept
    if not hasattr(module, "apply_assets"):
        raise TypeError(
            f"recipe {recipe_name(concept)!r} is used with source: hybrid but has no "
            f"apply_assets(); only asset recipes can back a hybrid concept"
        )

    dry_run = comfyui.dry_run_mode() if dry_run is None else dry_run
    available = comfyui.comfyui_available()
    if not available:
        print("ComfyUI sandbox not available — writing stub look assets")

    produced: dict[str, Path] = {}
    for job in jobs:
        target = Path(job["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            print(f"  asset: {job['name']} -> {target} (cached)")
            produced[job["param"]] = target
            continue
        if dry_run:
            print(f"  asset: {job['name']} (dry run — not generated)")
            continue
        if available:
            files = comfyui.run_workflow(
                job["workflow"], resolve_overrides(job["workflow"], job["inputs"]),
                target.parent,
            )
            image = _pick(files, IMAGE_SUFFIXES)
            if image is None:
                raise RuntimeError(
                    f"{job['name']}: {job['workflow']} produced no image "
                    f"(got: {[f.name for f in files] or 'nothing'})"
                )
            if image != target:
                shutil.move(str(image), target)
        else:
            comfyui.stub_still(target, job["name"], width=1344, height=768)
        produced[job["param"]] = target
        print(f"  asset: {job['name']} -> {target}")

    return module.apply_assets(concept, produced)
