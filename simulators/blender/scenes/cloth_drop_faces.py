"""
Cloth by Faces — gold cloth dropped onto a wooden box with a square hole.

Imitation of the Kawaken_3DCG Short "Cloth Simulation by different Faces":
a metallic sheet falls onto a hollow wooden pedestal and sags into the square
hole. As the mesh face count rises (16 -> 64 -> 256 -> 1024) the same drop goes
from a stiff, faceted metal plate to a soft cloth pouch. A big number over a
blue sky shows the current face count.

Built by copying scenes/_staged_demo_template.py and customizing the three
CUSTOMIZE points (material, per-stage subject, and the box collider). See that
template for the full contract documentation.

Params:
  face_counts: list[int]     stages (default [16, 64, 256, 1024])
  stage_duration_sec: float  seconds per stage (default 5.0)
  cloth_stiffness: float     tension/compression (default 8.0; lower = softer)
  cloth_mass: float          per-vertex-ish mass (default 0.3; higher = heavier drape)
  sheet_size: float          cloth square size in metres (default 1.9)
  drop_height: float         how far above the box the cloth starts (default 0.6)
  box_size: float            outer footprint of the pedestal (default 2.2)
  box_height: float          pedestal body height (default 1.4)
  hole_size: float           square opening the cloth sags into (default 1.1)
  gold_color: [r,g,b]        cloth base colour (default warm gold)
  wood_color: [r,g,b]        pedestal base colour (default oak brown)
  environment / world_hdri / camera_* / label_*  — see template.
"""

from __future__ import annotations

import math
from pathlib import Path

# --- scene identity ---------------------------------------------------------
STAGE_PARAM = "face_counts"
DEFAULT_STAGE_VALUES = [16, 64, 256, 1024]
KEEP_PREFIXES = ("Camera", "Key", "Fill", "Rim", "Sun", "Studio_", "Chaosim")


def _faces_to_subdivisions(faces: int) -> int:
    """Map a target face count to grid subdivisions (faces ~= (n-1)^2)."""
    side = max(2, int(round(math.sqrt(max(1, int(faces))))))
    return side + 1


def _actual_faces(subdivisions: int) -> int:
    return max(1, (subdivisions - 1) ** 2)


def _repo_root() -> Path:
    # scenes/ -> blender/ -> simulators/ -> repo root
    return Path(__file__).resolve().parents[3]


def _resolve_hdri_path(spec) -> Path:
    """Accept an absolute path, a repo-relative path, or a bare filename that
    is looked up under assets/hdri/."""
    p = Path(str(spec))
    if p.is_absolute() and p.exists():
        return p
    root = _repo_root()
    for cand in (root / p, root / "assets" / "hdri" / p.name):
        if cand.exists():
            return cand
    return root / p  # let the caller surface a clear load error


# --- keyframe interpolation compat (Blender 4 + 5) -------------------------
def set_linear_interpolation(obj) -> None:
    ad = getattr(obj, "animation_data", None)
    if ad is None or ad.action is None:
        return
    action = ad.action
    fcurves = getattr(action, "fcurves", None)
    if fcurves is None:
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
            hdri = _resolve_hdri_path(params["world_hdri"])
            tex = nt.nodes.new("ShaderNodeTexEnvironment")
            tex.image = bpy.data.images.load(str(hdri))
            # Mapping so the sky can be rotated to place the sun/clouds.
            tc = nt.nodes.new("ShaderNodeTexCoord")
            mp = nt.nodes.new("ShaderNodeMapping")
            rot_z = math.radians(float(params.get("hdri_rotation_deg", 0.0)))
            mp.inputs["Rotation"].default_value = (0.0, 0.0, rot_z)
            nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
            nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
            nt.links.new(tex.outputs["Color"], bg.inputs["Color"])
            print(f"  HDRI world: {hdri}")
            return
        except Exception as exc:  # noqa: BLE001
            print(f"  HDRI load failed ({exc}); falling back to sky")
            env = "sky"

    if env == "solid":
        c = params.get("world_color", [0.55, 0.72, 0.95])
        bg.inputs["Color"].default_value = (c[0], c[1], c[2], 1.0)
        return

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


def setup_color_management(params: dict) -> None:
    """Filmic tonemap so bright HDRI + gold don't blow out. Baked into the scene
    so both the CLI runner and interactive renders produce the same look."""
    import bpy

    scene = bpy.context.scene
    want = str(params.get("view_transform", "AgX"))
    for cand in (want, "AgX", "Filmic", "Standard"):
        try:
            scene.view_settings.view_transform = cand
            break
        except TypeError:
            continue
    try:
        scene.view_settings.look = "None"
    except Exception:
        pass
    scene.view_settings.exposure = float(params.get("exposure", -0.3))
    scene.view_settings.gamma = float(params.get("gamma", 1.0))


def setup_lights(params: dict, center=(0.0, 0.0, 0.0)) -> None:
    import sys
    from pathlib import Path as _Path

    import bpy

    sys.path.insert(0, str(_Path(__file__).parent.parent))
    from utils import add_area_light

    sun_data = bpy.data.lights.new("Sun", type="SUN")
    sun_data.energy = float(params.get("sun_energy", 3.2))
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = (math.radians(52), math.radians(8), math.radians(30))
    bpy.context.scene.collection.objects.link(sun)

    add_area_light(
        location=(center[0] - 3.0, center[1] - 3.5, center[2] + 3.5),
        energy=350, size=3.0, size_y=2.5, name="Fill",
        color=(1.0, 0.98, 0.95), look_at=center,
    )
    add_area_light(
        location=(center[0] + 2.5, center[1] + 3.0, center[2] + 2.5),
        energy=220, size=2.5, size_y=2.0, name="Rim",
        color=(0.95, 0.97, 1.0), look_at=center,
    )


def setup_camera(params: dict):
    import sys
    from pathlib import Path as _Path

    sys.path.insert(0, str(_Path(__file__).parent.parent))
    from utils import setup_camera as _setup_camera

    dist = float(params.get("camera_distance", 2.8))
    height = float(params.get("camera_height", 1.9))
    pitch = float(params.get("camera_pitch_deg", 58.0))
    lens = float(params.get("camera_lens", 30.0))

    cam = _setup_camera(location=(0.0, -dist, height), rotation_degrees=(pitch, 0, 0))
    cam.data.lens = lens
    cam.data.clip_start = 0.02
    cam.data.clip_end = 1000.0
    cam.data.sensor_fit = "AUTO"
    return cam


# --- big centered number ----------------------------------------------------
def add_center_number(value, params: dict):
    import bpy

    text = str(params.get("label_format", "{value}")).format(value=value)
    size = float(params.get("label_size", 0.55))
    z = float(params.get("label_height", 2.3))

    bpy.ops.object.text_add(location=(0.0, 0.2, z))
    label = bpy.context.active_object
    label.name = "StageNumber"
    label.data.body = text
    label.data.size = size
    label.data.align_x = "CENTER"
    label.data.align_y = "CENTER"
    label.data.extrude = 0.012
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
    import bpy

    for obj in list(bpy.data.objects):
        if any(obj.name.startswith(p) for p in KEEP_PREFIXES):
            continue
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and getattr(data, "users", 0) == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)


# ===========================================================================
# CUSTOMIZE 1 — gold metallic cloth material.
# ===========================================================================
def _set_input(bsdf, name: str, value) -> None:
    """Set a Principled BSDF input if this Blender version exposes it."""
    if name in bsdf.inputs:
        bsdf.inputs[name].default_value = value


def make_subject_material(params: dict):
    """Gold: a full metallic PBR setup (base colour, metallic, roughness, IOR,
    anisotropy) plus a fine procedural fabric normal so the sheet reads as woven
    metal cloth rather than flat chrome."""
    import bpy

    gold = params.get("gold_color", [1.0, 0.62, 0.13])
    rough = float(params.get("gold_roughness", 0.32))
    mat = bpy.data.materials.new("GoldCloth")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]

    _set_input(bsdf, "Base Color", (gold[0], gold[1], gold[2], 1.0))
    _set_input(bsdf, "Metallic", 1.0)
    _set_input(bsdf, "Roughness", rough)
    _set_input(bsdf, "IOR", 0.47)              # gold-ish
    _set_input(bsdf, "Anisotropic", 0.35)
    _set_input(bsdf, "Coat Weight", 0.0)

    # Micro fabric weave -> Bump -> Normal
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    _set_input(noise, "Scale", float(params.get("fabric_scale", 190.0)))
    _set_input(noise, "Detail", 2.0)
    bump = nt.nodes.new("ShaderNodeBump")
    _set_input(bump, "Strength", float(params.get("fabric_bump", 0.06)))
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def _make_wood_material(params: dict):
    """Wood: procedural grain (Wave + Noise distortion -> ColorRamp) driving base
    colour and a bump, with dielectric PBR values. No texture files needed."""
    import bpy

    wood = params.get("wood_color", [0.36, 0.22, 0.11])
    dark = [c * 0.6 for c in wood]
    mat = bpy.data.materials.new("WoodBox")
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]

    _set_input(bsdf, "Roughness", float(params.get("wood_roughness", 0.5)))
    _set_input(bsdf, "Metallic", 0.0)
    _set_input(bsdf, "IOR", 1.45)
    _set_input(bsdf, "Specular IOR Level", 0.35)

    tc = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0, 1.0, 3.0)   # stretch grain along Z
    wave = nodes.new("ShaderNodeTexWave")
    try:
        wave.wave_type = "BANDS"
        wave.bands_direction = "Z"
    except Exception:
        pass
    _set_input(wave, "Scale", float(params.get("wood_grain_scale", 4.0)))
    _set_input(wave, "Distortion", float(params.get("wood_grain_distortion", 1.5)))
    _set_input(wave, "Detail", 2.0)
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (dark[0], dark[1], dark[2], 1.0)
    ramp.color_ramp.elements[1].color = (wood[0], wood[1], wood[2], 1.0)
    bump = nodes.new("ShaderNodeBump")
    _set_input(bump, "Strength", 0.18)

    links.new(tc.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(wave.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def _build_box_with_hole(params: dict):
    """Wooden pedestal with a square shaft through the top (cloth sags into it)."""
    import bpy

    box_size = float(params.get("box_size", 2.2))
    box_h = float(params.get("box_height", 1.4))
    hole = float(params.get("hole_size", 1.1))

    # Solid body: top face sits at z = 0, extends down to -box_h.
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, -box_h / 2.0))
    base = bpy.context.active_object
    base.name = "Pedestal"
    base.scale = (box_size, box_size, box_h)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # Cutter: a BLIND square well (floor at -hole_depth) so even a very floppy
    # high-face-count sheet pouches into the hole instead of falling clean
    # through. box_height must exceed hole_depth to leave a floor.
    hole_depth = float(params.get("hole_depth", box_h * 0.8))
    top_over = 0.3                      # extend above the top for a clean rim
    cut_h = top_over + hole_depth
    cz = top_over - cut_h / 2.0         # -> well floor sits at z = -hole_depth
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, cz))
    cutter = bpy.context.active_object
    cutter.name = "HoleCutter"
    cutter.scale = (hole, hole, cut_h)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    bpy.context.view_layer.objects.active = base
    boolean = base.modifiers.new("Hole", type="BOOLEAN")
    boolean.operation = "DIFFERENCE"
    boolean.object = cutter
    try:
        bpy.ops.object.modifier_apply(modifier="Hole")
        bpy.data.objects.remove(cutter, do_unlink=True)
    except Exception as exc:  # noqa: BLE001
        print(f"  boolean hole failed ({exc}); keeping solid top")
        base.modifiers.remove(boolean)
        bpy.data.objects.remove(cutter, do_unlink=True)

    # Boolean can leave an empty material slot from the (unmaterialed) cutter,
    # which renders as default white. Reset slots and force wood on every face.
    base.data.materials.clear()
    base.data.materials.append(_make_wood_material(params))
    for poly in base.data.polygons:
        poly.material_index = 0
        poly.use_smooth = False

    # Collider so the cloth catches on the rim and drapes into the shaft.
    base.modifiers.new("Collision", type="COLLISION")
    if hasattr(base, "collision") and base.collision is not None:
        base.collision.thickness_outer = 0.025
        base.collision.thickness_inner = 0.025
        base.collision.cloth_friction = 12.0
    return base


# ===========================================================================
# CUSTOMIZE 2 — per-stage subject: box + gold cloth dropped over the hole.
# ===========================================================================
def build_stage_subject(value, *, frame_start: int, frame_end: int, params: dict) -> dict:
    import bpy

    _build_box_with_hole(params)

    subdivs = _faces_to_subdivisions(value)
    display_faces = _actual_faces(subdivs)
    sheet_size = float(params.get("sheet_size", 1.9))
    drop_h = float(params.get("drop_height", 0.6))
    stiffness = float(params.get("cloth_stiffness", 8.0))

    # Cloth grid starts flat, just above the hole, and free-falls under gravity.
    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=subdivs, y_subdivisions=subdivs, size=sheet_size,
        location=(0.0, 0.0, drop_h),
    )
    sheet = bpy.context.active_object
    sheet.name = "Cloth"
    sheet.data.materials.append(make_subject_material(params))
    for poly in sheet.data.polygons:
        poly.use_smooth = display_faces >= 256  # low counts read as facets

    cloth = sheet.modifiers.new(name="Cloth", type="CLOTH")
    s = cloth.settings
    # Higher solver substeps stop the fine high-face sheet from tunnelling
    # through the thin rim of the hole.
    s.quality = int(params.get("cloth_quality", 18))
    s.mass = float(params.get("cloth_mass", 0.3))
    s.tension_stiffness = stiffness
    s.compression_stiffness = stiffness
    s.shear_stiffness = stiffness * 0.7
    # Bending resists the fine, floppy high-face sheet from funnelling straight
    # through the hole; a metallic sheet is genuinely a bit stiff, so this also
    # reads more correct. Tunable; scales up a little with face count.
    s.bending_stiffness = float(params.get("cloth_bending", max(2.5, stiffness * 1.2)))
    cloth.collision_settings.use_collision = True
    cloth.collision_settings.distance_min = 0.025
    cloth.collision_settings.collision_quality = int(params.get("collision_quality", 12))
    _sc = params.get("self_collision")
    cloth.collision_settings.use_self_collision = (display_faces >= 64) if _sc is None else bool(_sc)
    if hasattr(cloth.collision_settings, "self_distance_min"):
        cloth.collision_settings.self_distance_min = 0.008
    cloth.point_cache.frame_start = frame_start
    cloth.point_cache.frame_end = frame_end

    solid = sheet.modifiers.new(name="Solidify", type="SOLIDIFY")
    solid.thickness = 0.01
    solid.offset = 0.0

    return {"bake": [sheet], "center": (0.0, 0.0, -0.2), "display_faces": display_faces}


# --- baking -----------------------------------------------------------------
def bake_targets(objs, frame_start: int, frame_end: int) -> None:
    import bpy

    if not objs:
        return
    scene = bpy.context.scene
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    for obj in objs:
        cloth = next((m for m in obj.modifiers if m.type in {"CLOTH", "SOFT_BODY"}), None)
        if cloth is None:
            continue
        cache = cloth.point_cache
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
    print(f"  baked cloth frames {frame_start}-{frame_end}")


# --- pipeline contract ------------------------------------------------------
def _stage_values(params: dict) -> list:
    vals = params.get(STAGE_PARAM) or params.get("stage_values") or DEFAULT_STAGE_VALUES
    return [int(v) for v in vals]


def setup_scene(params: dict):
    import sys
    from pathlib import Path as _Path

    import bpy

    sys.path.insert(0, str(_Path(__file__).parent.parent))
    from utils import clear_scene

    clear_scene()
    setup_environment(params)
    setup_color_management(params)
    setup_lights(params)
    setup_camera(params)

    values = _stage_values(params)
    value = values[0] if values else 16
    fps = bpy.context.scene.render.fps or 60
    stage_frames = max(1, int(float(params.get("stage_duration_sec", 5.0)) * fps))
    result = build_stage_subject(value, frame_start=1, frame_end=stage_frames, params=params)
    # The face-count number is added in compositing by default (crisp, restylable,
    # no re-render). Set label_in_scene: true to bake a 3D number instead.
    if params.get("label_in_scene", False):
        add_center_number(value, params)
    setup_scene._bake = result.get("bake", [])
    setup_scene._range = (1, stage_frames)


def run_simulation():
    objs = getattr(setup_scene, "_bake", [])
    f0, f1 = getattr(setup_scene, "_range", (1, 1))
    bake_targets(objs, f0, f1)


def render_staged(params: dict, frames_dir: Path):
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
    setup_color_management(params)
    setup_lights(params)
    setup_camera(params)

    scene.render.filepath = str(Path(frames_dir) / "frame_")
    scene.frame_start = 1
    scene.frame_end = total
    print(f"cloth_drop_faces staged: {len(values)} stages x {stage_frames} frames (total {total})")

    for i, value in enumerate(values):
        f0 = i * stage_frames + 1
        f1 = (i + 1) * stage_frames
        print(f"  Stage {i + 1}/{len(values)}: faces={value}, frames {f0}-{f1}")
        clear_stage_objects()
        result = build_stage_subject(value, frame_start=f0, frame_end=f1, params=params)
        if params.get("label_in_scene", False):
            add_center_number(value, params)
        print(f"    actual faces={result.get('display_faces')}")
        bake_targets(result.get("bake", []), f0, f1)

        scene.frame_start = f0
        scene.frame_end = f1
        scene.frame_set(f0)
        bpy.ops.render.render(animation=True)

    scene.frame_start = 1
    scene.frame_end = total
    print(f"cloth_drop_faces staged render complete -> {frames_dir}")


def collect_impact_events() -> list:
    """Cloth drape has no sharp hits; SFX handled later (see docs/sfx-design.md)."""
    return []
