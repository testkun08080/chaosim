"""
Blender entry point. Run as:
  blender --background --python simulators/blender/runner.py -- <concept.yaml> <output.mp4> <preset>

This script runs inside Blender's Python context.
"""

import sys
import os
import importlib.util
from pathlib import Path

# Parse args after "--"
argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
else:
    print("Usage: blender --background --python runner.py -- concept.yaml output.mp4 preset")
    sys.exit(1)

concept_path = Path(argv[0])
output_path = Path(argv[1])
preset_name = argv[2] if len(argv) > 2 else "medium"

# Prefer JSON (pipeline writes a sidecar so Blender needs no PyYAML).
# Fall back to YAML when a .yaml concept is passed directly.
import json

if concept_path.suffix.lower() == ".json":
    with open(concept_path, encoding="utf-8") as f:
        concept = json.load(f)
else:
    try:
        import yaml
        with open(concept_path, encoding="utf-8") as f:
            concept = yaml.safe_load(f)
    except ImportError:
        print("ERROR: PyYAML is not available in Blender Python. "
              "Pass a .json concept (pipeline/renderer.py does this automatically).")
        sys.exit(1)

scene_script_name = concept.get("scene_script", "double_pendulum")
params = concept.get("params", {})
duration_sec = concept.get("duration_sec", 15)

# Load render preset (JSON sidecar preferred; YAML optional).
preset_path = Path(__file__).parent.parent.parent / "config" / "render_presets.yaml"
preset_json = Path(__file__).parent.parent.parent / "config" / "render_presets.json"
_DEFAULT_PRESETS = {
    "preview": {"samples": 32, "resolution_percentage": 50, "fps": 30, "denoise": False},
    "medium": {"samples": 128, "resolution_percentage": 100, "fps": 60, "denoise": True},
    "high": {"samples": 512, "resolution_percentage": 100, "fps": 60, "denoise": True},
    "ultra": {"samples": 2048, "resolution_percentage": 100, "fps": 60, "denoise": True},
}
render_settings = dict(_DEFAULT_PRESETS.get(preset_name, _DEFAULT_PRESETS["medium"]))
try:
    if preset_json.exists():
        with open(preset_json, encoding="utf-8") as f:
            presets = json.load(f)
        render_settings = presets.get(preset_name, presets.get("medium", render_settings))
    else:
        import yaml
        with open(preset_path, encoding="utf-8") as f:
            presets = yaml.safe_load(f)
        render_settings = presets.get(preset_name, presets.get("medium", render_settings))
except Exception:
    pass

# Load and run scene script
scenes_dir = Path(__file__).parent / "scenes"
scene_file = scenes_dir / f"{scene_script_name}.py"

if not scene_file.exists():
    print(f"ERROR: Scene script not found: {scene_file}")
    sys.exit(1)

spec = importlib.util.spec_from_file_location("scene", scene_file)
scene_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene_module)

# Apply render settings
import bpy
import subprocess
import shutil

scene = bpy.context.scene
# Resolve a working engine. Blender 5.x may expose EEVEE as BLENDER_EEVEE.
# CHAOSIM_RENDER_ENGINE pins the engine. Headless CI has no GPU/GL context, so
# EEVEE there either aborts or emits black frames that still mux successfully —
# set this to CYCLES on a hosted runner. Unset keeps the autodetect order.
forced_engine = os.environ.get("CHAOSIM_RENDER_ENGINE", "").strip().upper()
if forced_engine:
    try:
        scene.render.engine = forced_engine
    except TypeError:
        print(f"ERROR: CHAOSIM_RENDER_ENGINE={forced_engine!r} is not available "
              f"in this Blender build")
        sys.exit(1)
else:
    for candidate in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
        try:
            scene.render.engine = candidate
            break
        except TypeError:
            continue

scene.render.resolution_x = 1080
scene.render.resolution_y = 1920
scene.render.resolution_percentage = int(render_settings.get("resolution_percentage", 100))
scene.render.fps = int(render_settings.get("fps", 60))
if scene.render.engine == "CYCLES" and hasattr(scene, "cycles"):
    scene.cycles.samples = int(render_settings.get("samples", 128))
    scene.cycles.use_denoising = bool(render_settings.get("denoise", True))
    try:
        scene.cycles.device = "CPU"
    except Exception:
        pass

# Blender 5.x image format enums vary by build/addons. Render a PNG sequence,
# then mux to MP4 with system ffmpeg for a stable output contract.
frames_dir = output_path.parent / f"{output_path.stem}_frames"
if frames_dir.exists():
    shutil.rmtree(frames_dir)
frames_dir.mkdir(parents=True, exist_ok=True)

scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.filepath = str(frames_dir / "frame_")
scene.frame_start = 1
scene.frame_end = max(1, int(duration_sec * scene.render.fps))

# CI cost guardrail: cap the frame count so a long concept cannot burn the whole
# job budget before failing. Staged scenes (render_staged) recompute frame_end
# themselves below and are not covered by this cap.
max_frames = int(os.environ.get("CHAOSIM_MAX_FRAMES", "0") or 0)
if max_frames > 0 and scene.frame_end > max_frames:
    print(f"CHAOSIM_MAX_FRAMES={max_frames}: truncating frame_end "
          f"{scene.frame_end} -> {max_frames}")
    scene.frame_end = max_frames

print(f"Engine={scene.render.engine} frames={scene.frame_start}-{scene.frame_end} "
      f"res%={scene.render.resolution_percentage} fps={scene.render.fps}")

# Optional SFX timing sidecar (written after setup when available).
events_path = output_path.parent / f"{output_path.stem}_events.json"

# Staged scenes (e.g. paper_to_cloth) own their bake+render loop.
if hasattr(scene_module, "render_staged"):
    # Align duration with stage math when the scene declares face_counts.
    face_counts = params.get("face_counts")
    stage_sec = float(params.get("stage_duration_sec", 0) or 0)
    if face_counts and stage_sec > 0:
        staged_end = max(1, int(len(face_counts) * stage_sec * scene.render.fps))
        scene.frame_end = staged_end
        print(f"Staged frame_end override -> {staged_end}")
    scene_module.render_staged(params, frames_dir)
    events_path.write_text(json.dumps({"events": []}), encoding="utf-8")
else:
    scene_module.setup_scene(params)
    scene_module.run_simulation()

    if hasattr(scene_module, "collect_impact_events"):
        try:
            events = scene_module.collect_impact_events()
            events_path.write_text(
                json.dumps({"events": events, "fps": scene.render.fps}, indent=2),
                encoding="utf-8",
            )
            print(f"Wrote {len(events)} SFX events -> {events_path}")
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: collect_impact_events failed: {exc}")
            events_path.write_text(json.dumps({"events": []}), encoding="utf-8")
    else:
        events_path.write_text(json.dumps({"events": []}), encoding="utf-8")

    # Render animation frames
    bpy.ops.render.render(animation=True)

ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
fps = scene.render.fps
cmd = [
    ffmpeg, "-y",
    "-framerate", str(fps),
    "-i", str(frames_dir / "frame_%04d.png"),
    "-c:v", "libx264", "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    str(output_path),
]
print("Mux:", " ".join(cmd))
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(result.stderr)
    raise RuntimeError(f"ffmpeg mux failed ({result.returncode})")

# Keep disk usage small for preview runs.
shutil.rmtree(frames_dir, ignore_errors=True)
print(f"Render complete: {output_path}")
