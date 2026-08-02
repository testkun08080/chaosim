"""Bake-only helper: write SFX events without rendering frames.

Usage:
  blender --background --python scripts/bake_sfx_events.py -- <concept.json> <events.json>
"""

import importlib.util
import json
import sys
from pathlib import Path

argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
else:
    print("Usage: blender --background --python scripts/bake_sfx_events.py -- concept.json events.json")
    sys.exit(1)

concept_path = Path(argv[0])
events_path = Path(argv[1]) if len(argv) > 1 else concept_path.with_name(
    concept_path.stem.replace("_concept", "") + "_events.json"
)

with open(concept_path, encoding="utf-8") as f:
    concept = json.load(f)

params = concept.get("params", {})
duration = float(concept.get("duration_sec", 6))
scene_name = concept.get("scene_script", "domino_chain")

import bpy

scene = bpy.context.scene
for candidate in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
    try:
        scene.render.engine = candidate
        break
    except TypeError:
        continue
scene.render.fps = 30
scene.frame_start = 1
scene.frame_end = max(1, int(duration * scene.render.fps))

scene_file = Path(__file__).resolve().parent.parent / "simulators" / "blender" / "scenes" / f"{scene_name}.py"
if not scene_file.exists():
    print(f"ERROR: scene not found: {scene_file}")
    sys.exit(1)

spec = importlib.util.spec_from_file_location("scene", scene_file)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.setup_scene(params)
sys.path.insert(0, str(scene_file.parent.parent))
from utils import call_run_simulation  # noqa: E402
call_run_simulation(mod, params)

if not hasattr(mod, "collect_impact_events"):
    events = []
else:
    events = mod.collect_impact_events()

events_path.parent.mkdir(parents=True, exist_ok=True)
events_path.write_text(
    json.dumps({"events": events, "fps": scene.render.fps}, indent=2),
    encoding="utf-8",
)
print(f"Wrote {len(events)} events -> {events_path}")
