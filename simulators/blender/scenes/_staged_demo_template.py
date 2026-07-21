"""
TEMPLATE — Staged comparison demo (copy me).

A reusable scaffold for "watch this change as a number goes up" Shorts, in the
Kawaken / Kintsugi style. It renders N stages back-to-back; each stage rebuilds
the subject for a different value (e.g. face count) and shows that value as a big
centered number over a sky background.

To make a new scene:
  1. Copy this file to  simulators/blender/scenes/<your_scene>.py
  2. Register "<your_scene>" in  simulators/blender/__init__.py  (AVAILABLE_SCENES)
  3. Edit the three CUSTOMIZE points below:
        - make_subject_material()     what the subject looks like
        - build_stage_subject()       the per-stage geometry + physics
        - (optional) STAGE_PARAM / defaults, environment, camera
  4. Write a concept YAML with  scene_script: <your_scene>

Contract expected by the pipeline (see simulators/blender/runner.py):
  setup_scene(params)          single-stage build (GUI preview / non-staged path)
  run_simulation()             bake the single stage
  render_staged(params, dir)   full multi-stage bake+render loop  (staged path)
  collect_impact_events()      optional -> [] here (no discrete impacts)

Self-contained: no relative imports except the sibling ``utils`` module, loaded
the same way every scene in this repo does (sys.path insert). Runs inside
Blender's Python.

Common params (all optional, with defaults):
  stage_values: list        the values to iterate (default [16, 64, 256, 1024])
  stage_duration_sec: float seconds per stage (default 5.0)
  environment: str          "sky" | "hdri" | "solid"      (default "sky")
  world_hdri: str           path to .hdr/.exr when environment == "hdri"
  world_color: [r,g,b]      background when environment == "solid"
  world_strength: float     environment light strength (default 1.0)
  sun_elevation_deg: float  Nishita sun height for "sky" (default 25)
  camera_lens: float        mm (default 30)
  camera_distance: float    (default 2.6)
  camera_height: float      (default 1.6)
  camera_pitch_deg: float   90 = level, <90 looks down (default 60)
  label_size: float         3D number height in metres (default 0.5)
  label_height: float       world Z of the number (default 2.4)
"""

from __future__ import annotations

import math
from pathlib import Path

# --- scene identity (override in a copy) -----------------------------------
STAGE_PARAM = "stage_values"
DEFAULT_STAGE_VALUES = [16, 64, 256, 1024]
KEEP_PREFIXES = ("Camera", "Key", "Fill", "Rim", "Sun", "Studio_", "Chaosim")


# --- keyframe interpolation compat (Blender 4 + 5) -------------------------
def set_linear_interpolation(obj) -> None:
    """Force LINEAR interpolation on an object's keyframes (version-safe)."""
    ad = getattr(obj, "animation_data", None)
    if ad is None or ad.action is None:
        return
    action = ad.action
    fcurves = getattr(action, "fcurves", None)
    if fcurves is None:  # Blender 5 layered actions
        try:
            for layer in action.layers:
                for strip in layer.strips:
                    channelbag = strip.channelbag(ad.action_slot, ensure=False)
                    if channelbag is not None:
                        fcurves = channelbag.fcurves
                        break
                if fcurves is not None:
                    break
        except Exception:
            return
    for fc in fcurves or []:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


# --- environment (sky / hdri / solid) --------------------------------------
def setup_environment(params: dict) -> None:
    """Build the world. Default is a clear Nishita sky (closest robust match to
    the 'floating over the sky' look without shipping an HDRI)."""
    import bpy

    env = str(params.get("environment", "sky")).lower()
    strength = float(params.get("world_strength", 1.0))

    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    if env == "hdri" and params.get("world_hdri"):
        try:
            tex = nt.nodes.new("ShaderNodeTexEnvironment")
            tex.image = bpy.data.images.load(str(params["world_hdri"]))
            nt.links.new(tex.outputs["Color"], bg.inputs["Color"])
            return
        except Exception as exc:  # noqa: BLE001
            print(f"  HDRI load failed ({exc}); falling back to sky")
            env = "sky"

    if env == "solid":
        c = params.get("world_color", [0.55, 0.72, 0.95])
        bg.inputs["Color"].default_value = (c[0], c[1], c[2], 1.0)
        return

    # Default: procedural sky.
    try:
        sky = nt.nodes.new("ShaderNodeTexSky")
        try:
            sky.sky_type = "NISHITA"
            sky.sun_elevation = math.radians(float(params.get("sun_elevation_deg", 25.0)))
        except Exception:
            pass
        nt.links.new(sky.outputs[0], bg.inputs["Color"])
    except Exception:
        bg.inputs["Color"].default_value = (0.55, 0.72, 0.95, 1.0)


def setup_lights(params: dict, center=(0.0, 0.0, 0.0)) -> None:
    """Sun + soft area fill. Reuses the shared area-light helper."""
    import sys
    from pathlib import Path as _Path

    import bpy

    sys.path.insert(0, str(_Path(__file__).parent.parent))
    from utils import add_area_light

    sun_data = bpy.data.lights.new("Sun", type="SUN")
    sun_data.energy = float(params.get("sun_energy", 3.0))
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = (math.radians(52), math.radians(8), math.radians(30))
    bpy.context.scene.collection.objects.link(sun)

    add_area_light(
        location=(center[0] - 3.0, center[1] - 3.5, center[2] + 3.5),
        energy=300, size=3.0, size_y=2.5, name="Fill",
        color=(1.0, 0.98, 0.95), look_at=center,
    )


def setup_camera(params: dict):
    """Shorts 9:16 framing. Elevated, looking down at the subject."""
    import sys
    from pathlib import Path as _Path

    sys.path.insert(0, str(_Path(__file__).parent.parent))
    from utils import setup_camera as _setup_camera

    dist = float(params.get("camera_distance", 2.6))
    height = float(params.get("camera_height", 1.6))
    pitch = float(params.get("camera_pitch_deg", 60.0))
    lens = float(params.get("camera_lens", 30.0))

    cam = _setup_camera(location=(0.0, -dist, height), rotation_degrees=(pitch, 0, 0))
    cam.data.lens = lens
    cam.data.clip_start = 0.02
    cam.data.clip_end = 1000.0
    cam.data.sensor_fit = "AUTO"
    return cam


# --- big centered number ----------------------------------------------------
def add_center_number(value, params: dict):
    """Emissive 3D number, floated high in frame, facing the camera (-Y)."""
    import bpy

    text = str(params.get("label_format", "{value}")).format(value=value)
    size = float(params.get("label_size", 0.5))
    z = float(params.get("label_height", 2.4))

    bpy.ops.object.text_add(location=(0.0, 0.2, z))
    label = bpy.context.active_object
    label.name = "StageNumber"
    label.data.body = text
    label.data.size = size
    label.data.align_x = "CENTER"
    label.data.align_y = "CENTER"
    label.data.extrude = 0.01
    label.rotation_euler = (math.radians(90), 0.0, 0.0)

    mat = bpy.data.materials.new("NumberMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 6.0
    label.data.materials.append(mat)
    return label


# --- stage teardown ---------------------------------------------------------
def clear_stage_objects() -> None:
    """Remove per-stage subjects but keep camera, lights and world."""
    import bpy

    for obj in list(bpy.data.objects):
        if any(obj.name.startswith(p) for p in KEEP_PREFIXES):
            continue
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and getattr(data, "users", 0) == 0:
            for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.cameras, bpy.data.lights):
                try:
                    if data.__class__.__name__.lower() in coll.rna_type.identifier.lower() or True:
                        coll.remove(data)
                        break
                except Exception:
                    continue


# ===========================================================================
# CUSTOMIZE 1/2 — the subject's material.
# ===========================================================================
def make_subject_material():
    """Default: a neutral matte. Override in a copy (e.g. gold metal)."""
    import bpy

    mat = bpy.data.materials.new("SubjectMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.85, 0.86, 0.9, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.4
    return mat


# ===========================================================================
# CUSTOMIZE 2/2 — build the subject for one stage.
# Return a dict:  {"bake": [objs to bake], "center": (x,y,z)}
# `value` is the current stage value (e.g. face count).
# ===========================================================================
def build_stage_subject(value, *, frame_start: int, frame_end: int, params: dict) -> dict:
    """Default demo: an icosphere whose subdivisions scale with `value`, slowly
    spinning so the stage has motion. Replace with your own geometry/physics."""
    import bpy

    subdiv = max(1, min(7, int(round(math.log2(max(2, int(value))) / 2))))
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdiv, radius=0.8, location=(0, 0, 0.8))
    obj = bpy.context.active_object
    obj.name = "Subject"
    for poly in obj.data.polygons:
        poly.use_smooth = False
    obj.data.materials.append(make_subject_material())

    # Spin across the stage for a little life.
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.keyframe_insert("rotation_euler", frame=frame_start)
    obj.rotation_euler = (0.0, 0.0, math.radians(180))
    obj.keyframe_insert("rotation_euler", frame=frame_end)
    set_linear_interpolation(obj)

    return {"bake": [], "center": (0.0, 0.0, 0.8)}


# --- baking (cloth / soft body / rigid body point caches) ------------------
def bake_targets(objs, frame_start: int, frame_end: int) -> None:
    """Bake point caches for any physics objects a stage returns."""
    import bpy

    if not objs:
        return
    scene = bpy.context.scene
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    for obj in objs:
        cache_mod = next((m for m in obj.modifiers if m.type in {"CLOTH", "SOFT_BODY"}), None)
        if cache_mod is None:
            continue
        cache = cache_mod.point_cache
        cache.frame_start = frame_start
        cache.frame_end = frame_end
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        try:
            override = bpy.context.copy()
            override["point_cache"] = cache
            with bpy.context.temp_override(**override):
                bpy.ops.ptcache.free_bake()
                bpy.ops.ptcache.bake(bake=True)
        except Exception:
            try:
                bpy.ops.ptcache.bake_all(bake=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  bake failed for {obj.name}: {exc}")
    print(f"  baked {len(objs)} object(s) frames {frame_start}-{frame_end}")


# --- pipeline contract ------------------------------------------------------
def _stage_values(params: dict) -> list:
    vals = params.get(STAGE_PARAM) or params.get("face_counts") or DEFAULT_STAGE_VALUES
    return [int(v) if str(v).isdigit() else v for v in vals]


def setup_scene(params: dict):
    """Single-stage build (GUI preview / non-staged runner path)."""
    import sys
    from pathlib import Path as _Path

    import bpy

    sys.path.insert(0, str(_Path(__file__).parent.parent))
    from utils import clear_scene

    clear_scene()
    setup_environment(params)
    setup_lights(params)
    setup_camera(params)

    values = _stage_values(params)
    value = values[0] if values else 16
    fps = bpy.context.scene.render.fps or 60
    stage_frames = max(1, int(float(params.get("stage_duration_sec", 5.0)) * fps))
    result = build_stage_subject(value, frame_start=1, frame_end=stage_frames, params=params)
    add_center_number(value, params)
    setup_scene._bake = result.get("bake", [])  # stash for run_simulation
    setup_scene._range = (1, stage_frames)


def run_simulation():
    """Bake the single stage built by setup_scene."""
    objs = getattr(setup_scene, "_bake", [])
    f0, f1 = getattr(setup_scene, "_range", (1, 1))
    bake_targets(objs, f0, f1)


def render_staged(params: dict, frames_dir: Path):
    """Multi-stage loop: for each value, rebuild -> bake -> render its frames."""
    import sys
    from pathlib import Path as _Path

    import bpy

    sys.path.insert(0, str(_Path(__file__).parent.parent))
    from utils import clear_scene

    values = _stage_values(params)
    scene = bpy.context.scene
    fps = scene.render.fps or 60
    stage_frames = max(1, int(float(params.get("stage_duration_sec", 5.0)) * fps))
    total = stage_frames * len(values)

    clear_scene()
    setup_environment(params)
    setup_lights(params)
    setup_camera(params)

    scene.render.filepath = str(Path(frames_dir) / "frame_")
    scene.frame_start = 1
    scene.frame_end = total
    print(f"staged demo: {len(values)} stages x {stage_frames} frames (total {total})")

    for i, value in enumerate(values):
        f0 = i * stage_frames + 1
        f1 = (i + 1) * stage_frames
        print(f"  Stage {i + 1}/{len(values)}: value={value}, frames {f0}-{f1}")
        clear_stage_objects()
        result = build_stage_subject(value, frame_start=f0, frame_end=f1, params=params)
        add_center_number(value, params)
        bake_targets(result.get("bake", []), f0, f1)

        scene.frame_start = f0
        scene.frame_end = f1
        scene.frame_set(f0)
        bpy.ops.render.render(animation=True)

    scene.frame_start = 1
    scene.frame_end = total
    print(f"staged demo render complete -> {frames_dir}")


def collect_impact_events() -> list:
    """No discrete impacts in the template. Override if your scene has hits."""
    return []
