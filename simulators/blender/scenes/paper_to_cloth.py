"""
Paper → Cloth face-count demo.

A pinned sheet hangs from a rod; a glass sphere pushes through it.
As mesh face count rises (16 → 64 → 256 → 1024), the sheet goes from
stiff paper-like to soft cloth-like — Kawaken-style satisfying Short.

Params:
  face_counts: list[int] (default [16, 64, 256, 1024])
  stage_duration_sec: float (default 6.0)
  sphere_radius: float (default 0.35)
  cloth_stiffness: float (default 15.0) — tension/compression/shear
  sheet_size: float (default 1.6)
  backdrop_color: [r, g, b] (default warm beige)
"""

from __future__ import annotations

import math
from pathlib import Path


def _set_linear_interpolation(obj) -> None:
    """Set all location keyframes to LINEAR (Blender 4/5 compatible)."""
    ad = getattr(obj, "animation_data", None)
    if ad is None or ad.action is None:
        return
    action = ad.action
    fcurves = getattr(action, "fcurves", None)
    if fcurves is None:
        # Blender 5 layered actions: channelbag fcurves
        try:
            for layer in action.layers:
                for strip in layer.strips:
                    channelbag = strip.channelbag(ad.action_slot, ensure=False)
                    if channelbag is None:
                        continue
                    fcurves = channelbag.fcurves
                    break
                if fcurves is not None:
                    break
        except Exception:
            return
    if not fcurves:
        return
    for fc in fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def _faces_to_subdivisions(faces: int) -> int:
    """Map target face count to grid subdivisions (faces ≈ (n-1)^2)."""
    side = max(2, int(round(math.sqrt(max(1, int(faces))))))
    return side + 1  # vertices along one edge


def _actual_faces(subdivisions: int) -> int:
    return max(1, (subdivisions - 1) ** 2)


def _set_world_color(color, strength: float = 1.0):
    import bpy

    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        r, g, b = color[0], color[1], color[2]
        bg.inputs["Color"].default_value = (r, g, b, 1.0)
        bg.inputs["Strength"].default_value = strength


def _make_sheet_material():
    import bpy

    mat = bpy.data.materials.new("SheetMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    # Bright paper — high contrast against warm backdrop
    bsdf.inputs["Base Color"].default_value = (0.96, 0.96, 0.94, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.72
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.12
    return mat


def _make_glass_material():
    import bpy

    mat = bpy.data.materials.new("GlassSphereMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    # Teal translucent glass (keep readable over the sheet)
    bsdf.inputs["Base Color"].default_value = (0.05, 0.85, 0.80, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.08
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = 0.75
    elif "Transmission" in bsdf.inputs:
        bsdf.inputs["Transmission"].default_value = 0.75
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = 1.45
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.05
    if "Alpha" in bsdf.inputs:
        bsdf.inputs["Alpha"].default_value = 0.9
        try:
            mat.blend_method = "BLEND"
        except TypeError:
            pass
    return mat


def _make_rod_material():
    import bpy

    mat = bpy.data.materials.new("RodMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.75, 0.78, 0.82, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.9
    bsdf.inputs["Roughness"].default_value = 0.25
    return mat


def _ensure_soft_lights(center=(0.0, 0.0, 0.2)):
    import sys
    from pathlib import Path as _Path

    sys.path.insert(0, str(_Path(__file__).parent.parent))
    from utils import add_area_light

    # Harder key so cloth facets catch highlights (Kawaken-style readability).
    add_area_light(
        location=(center[0] - 2.0, center[1] - 3.5, center[2] + 3.0),
        energy=480,
        size=2.5,
        size_y=2.0,
        name="ClothKey",
        color=(1.0, 0.98, 0.94),
        look_at=center,
    )
    add_area_light(
        location=(center[0] + 2.5, center[1] - 2.5, center[2] + 1.5),
        energy=160,
        size=4.0,
        size_y=3.5,
        name="ClothFill",
        color=(0.95, 0.97, 1.0),
        look_at=center,
    )
    add_area_light(
        location=(center[0], center[1] + 3.0, center[2] + 2.5),
        energy=220,
        size=2.5,
        size_y=1.5,
        name="ClothRim",
        color=(0.9, 0.95, 1.0),
        look_at=center,
    )


def _setup_camera(params: dict | None = None):
    """YouTube Shorts framing: phone-like FOV, frontal, subject-filled 9:16."""
    import sys
    from pathlib import Path as _Path

    import bpy

    sys.path.insert(0, str(_Path(__file__).parent.parent))
    from utils import setup_camera

    p = params or {}
    # Closer + wider than the old 45mm/3.8m telephoto look.
    # Explicit euler (no Track To) keeps the hanging sheet face-on.
    lens = float(p.get("camera_lens", 24.0))
    dist = float(p.get("camera_distance", 2.0))
    height = float(p.get("camera_height", 0.3))
    pitch = float(p.get("camera_pitch_deg", 86.0))

    cam = setup_camera(
        location=(0.0, -dist, height),
        rotation_degrees=(pitch, 0, 0),
    )
    cam.data.lens = lens
    cam.data.clip_start = 0.05
    cam.data.sensor_fit = "AUTO"
    return cam


def _clear_stage_objects():
    """Remove physics/label objects between stages; keep camera + lights + world."""
    import bpy

    keep_prefixes = ("Camera", "ClothKey", "ClothFill", "ClothRim")
    for obj in list(bpy.data.objects):
        if any(obj.name.startswith(p) for p in keep_prefixes):
            continue
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and getattr(data, "users", 0) == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)
            elif isinstance(data, bpy.types.Camera):
                bpy.data.cameras.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)


def _build_stage(
    faces: int,
    *,
    frame_start: int,
    frame_end: int,
    sphere_radius: float,
    cloth_stiffness: float,
    sheet_size: float,
):
    """Build rod + pinned sheet + glass sphere for one face-count stage."""
    import bpy

    subdivs = _faces_to_subdivisions(faces)
    display_faces = _actual_faces(subdivs)

    # --- Rod (visual pin bar) ---
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.02,
        depth=sheet_size * 1.2,
        location=(0.0, 0.0, sheet_size * 0.5),
    )
    rod = bpy.context.active_object
    rod.name = "Rod"
    rod.rotation_euler[1] = math.radians(90)
    rod.data.materials.append(_make_rod_material())

    # --- Sheet grid, hanging in XZ (facing -Y camera) ---
    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=subdivs,
        y_subdivisions=subdivs,
        size=sheet_size,
        location=(0.0, 0.0, 0.0),
    )
    sheet = bpy.context.active_object
    sheet.name = "Sheet"
    sheet.rotation_euler[0] = math.radians(90)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    sheet.location = (0.0, 0.0, 0.0)
    sheet.data.materials.append(_make_sheet_material())
    # Flat shading makes low face-counts read as “paper facets”
    for poly in sheet.data.polygons:
        poly.use_smooth = False

    mesh = sheet.data
    zs = [v.co.z for v in mesh.vertices]
    z_max = max(zs)
    pin_tol = (z_max - min(zs)) * 0.02 + 1e-4
    pin_group = sheet.vertex_groups.new(name="Pin")
    pin_indices = [v.index for v in mesh.vertices if v.co.z >= z_max - pin_tol]
    pin_group.add(pin_indices, 1.0, "REPLACE")

    # Cloth first, then Solidify so thickness follows the sim
    cloth = sheet.modifiers.new(name="Cloth", type="CLOTH")
    settings = cloth.settings
    settings.quality = 10
    settings.mass = 0.2
    settings.tension_stiffness = float(cloth_stiffness)
    settings.compression_stiffness = float(cloth_stiffness)
    settings.shear_stiffness = float(cloth_stiffness) * 0.7
    settings.bending_stiffness = max(0.5, float(cloth_stiffness) * 0.25)
    if hasattr(settings, "vertex_group_mass"):
        settings.vertex_group_mass = "Pin"
    settings.pin_stiffness = 1.0
    cloth.collision_settings.use_collision = True
    cloth.collision_settings.distance_min = 0.015
    cloth.collision_settings.collision_quality = 5
    cloth.collision_settings.use_self_collision = display_faces >= 64
    cloth.point_cache.frame_start = frame_start
    cloth.point_cache.frame_end = frame_end

    solid = sheet.modifiers.new(name="Solidify", type="SOLIDIFY")
    solid.thickness = 0.008
    solid.offset = 0.0

    # --- Glass sphere (collision) ---
    # Start just in front of sheet, push deep through for a clear bulge
    start_y = -sphere_radius - 0.25
    end_y = sphere_radius + 0.65
    z_hit = 0.0
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=sphere_radius,
        segments=48,
        ring_count=24,
        location=(0.0, start_y, z_hit),
    )
    sphere = bpy.context.active_object
    sphere.name = "GlassSphere"
    sphere.data.materials.append(_make_glass_material())
    for poly in sphere.data.polygons:
        poly.use_smooth = True
    sphere.modifiers.new(name="Collision", type="COLLISION")
    if hasattr(sphere, "collision") and sphere.collision is not None:
        sphere.collision.thickness_outer = 0.015
        sphere.collision.thickness_inner = 0.015

    # Animate: pause → push → hold
    span = max(1, frame_end - frame_start)
    t_start = frame_start + max(1, int(span * 0.08))
    t_end = frame_start + max(t_start + 1, int(span * 0.7))
    sphere.location = (0.0, start_y, z_hit)
    sphere.keyframe_insert("location", frame=frame_start)
    sphere.keyframe_insert("location", frame=t_start)
    sphere.location = (0.0, end_y, z_hit)
    sphere.keyframe_insert("location", frame=t_end)
    sphere.keyframe_insert("location", frame=frame_end)
    _set_linear_interpolation(sphere)

    # --- Face-count label: world-space above the rod (readable in 9:16) ---
    bpy.ops.object.text_add(location=(0.0, -0.05, sheet_size * 0.5 + 0.28))
    label = bpy.context.active_object
    label.name = "FacesLabel"
    label.data.body = f"{display_faces} Faces"
    label.data.size = 0.18
    label.data.align_x = "CENTER"
    label.data.align_y = "CENTER"
    label.data.extrude = 0.002
    label.rotation_euler = (math.radians(90), 0.0, 0.0)
    mat = bpy.data.materials.new("LabelMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 8.0
    label.data.materials.append(mat)

    return sheet, sphere, display_faces


def _bake_cloth(sheet):
    import bpy

    cloth = next((m for m in sheet.modifiers if m.type == "CLOTH"), None)
    if cloth is None:
        raise RuntimeError("Cloth modifier missing on Sheet")

    cache = cloth.point_cache
    scene = bpy.context.scene
    bpy.context.view_layer.objects.active = sheet
    sheet.select_set(True)

    # Free previous bake if any
    try:
        override = bpy.context.copy()
        override["point_cache"] = cache
        with bpy.context.temp_override(**override):
            bpy.ops.ptcache.free_bake()
    except Exception:
        try:
            bpy.ops.ptcache.free_bake_all()
        except Exception:
            pass

    try:
        override = bpy.context.copy()
        override["point_cache"] = cache
        with bpy.context.temp_override(**override):
            bpy.ops.ptcache.bake(bake=True)
    except Exception:
        # Fallback for older context handling
        bpy.ops.ptcache.bake_all(bake=True)

    print(f"  Cloth baked frames {cache.frame_start}-{cache.frame_end}")


def setup_scene(params: dict):
    """Single-stage setup (non-staged runner path / preview in GUI)."""
    import bpy

    from pathlib import Path as _Path
    import sys

    sys.path.insert(0, str(_Path(__file__).parent.parent))
    from utils import clear_scene

    clear_scene()

    backdrop = params.get("backdrop_color", [0.42, 0.32, 0.24])
    _set_world_color(backdrop, strength=1.0)
    _ensure_soft_lights()
    _setup_camera(params)

    face_counts = params.get("face_counts", [16, 64, 256, 1024])
    faces = int(face_counts[0]) if face_counts else 16
    fps = bpy.context.scene.render.fps or 60
    stage_sec = float(params.get("stage_duration_sec", 6.0))
    stage_frames = max(1, int(stage_sec * fps))

    _build_stage(
        faces,
        frame_start=1,
        frame_end=stage_frames,
        sphere_radius=float(params.get("sphere_radius", 0.35)),
        cloth_stiffness=float(params.get("cloth_stiffness", 12.0)),
        sheet_size=float(params.get("sheet_size", 1.6)),
    )


def run_simulation():
    """Bake cloth for the single-stage path."""
    import bpy

    sheet = bpy.data.objects.get("Sheet")
    if sheet is None:
        raise RuntimeError("Sheet object not found — call setup_scene first")
    _bake_cloth(sheet)


def render_staged(params: dict, frames_dir: Path):
    """Multi-stage face-count loop: rebuild → bake → render each stage."""
    import sys
    from pathlib import Path as _Path

    import bpy

    sys.path.insert(0, str(_Path(__file__).parent.parent))
    from utils import clear_scene

    face_counts = [int(f) for f in params.get("face_counts", [16, 64, 256, 1024])]
    stage_sec = float(params.get("stage_duration_sec", 6.0))
    sphere_radius = float(params.get("sphere_radius", 0.35))
    cloth_stiffness = float(params.get("cloth_stiffness", 12.0))
    sheet_size = float(params.get("sheet_size", 1.6))
    backdrop = params.get("backdrop_color", [0.42, 0.32, 0.24])

    scene = bpy.context.scene
    fps = scene.render.fps or 60
    stage_frames = max(1, int(stage_sec * fps))
    total_frames = stage_frames * len(face_counts)

    clear_scene()
    _set_world_color(backdrop, strength=1.0)
    _ensure_soft_lights()
    _setup_camera(params)

    scene.render.filepath = str(Path(frames_dir) / "frame_")
    scene.frame_start = 1
    scene.frame_end = total_frames

    print(f"paper_to_cloth staged: {len(face_counts)} stages × {stage_frames} frames "
          f"(total {total_frames})")

    for i, faces in enumerate(face_counts):
        f0 = i * stage_frames + 1
        f1 = (i + 1) * stage_frames
        print(f"  Stage {i + 1}/{len(face_counts)}: target={faces} faces, frames {f0}-{f1}")

        _clear_stage_objects()
        sheet, _sphere, display_faces = _build_stage(
            faces,
            frame_start=f0,
            frame_end=f1,
            sphere_radius=sphere_radius,
            cloth_stiffness=cloth_stiffness,
            sheet_size=sheet_size,
        )
        print(f"    actual faces={display_faces}")
        _bake_cloth(sheet)

        scene.frame_start = f0
        scene.frame_end = f1
        scene.frame_set(f0)
        bpy.ops.render.render(animation=True)

    scene.frame_start = 1
    scene.frame_end = total_frames
    print(f"paper_to_cloth staged render complete → {frames_dir}")
