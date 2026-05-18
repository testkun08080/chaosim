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

# Load YAML (blender ships with pyyaml in some builds; if not, use json)
try:
    import yaml
    with open(concept_path) as f:
        concept = yaml.safe_load(f)
except ImportError:
    import json
    # Fallback: expect JSON concept files
    with open(concept_path) as f:
        concept = json.load(f)

scene_script_name = concept.get("scene_script", "double_pendulum")
params = concept.get("params", {})
duration_sec = concept.get("duration_sec", 15)

# Load render preset
preset_path = Path(__file__).parent.parent.parent / "config" / "render_presets.yaml"
try:
    import yaml
    with open(preset_path) as f:
        presets = yaml.safe_load(f)
    render_settings = presets.get(preset_name, presets["medium"])
except Exception:
    render_settings = {"samples": 128, "resolution_percentage": 100, "fps": 60, "denoise": True}

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

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.render.resolution_x = 1080
scene.render.resolution_y = 1920
scene.render.resolution_percentage = render_settings.get("resolution_percentage", 100)
scene.render.fps = render_settings.get("fps", 60)
scene.cycles.samples = render_settings.get("samples", 128)
scene.cycles.use_denoising = render_settings.get("denoise", True)
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "HIGH"
scene.render.filepath = str(output_path)
scene.frame_end = int(duration_sec * scene.render.fps)

# Setup and run scene
scene_module.setup_scene(params)
scene_module.run_simulation()

# Render animation
bpy.ops.render.render(animation=True)
print(f"Render complete: {output_path}")
