"""
Soft Body Torus — 0% vs 100%.
Two (or more) identical tori sit side by side. A cylinder drops into each one at
the same instant. The left torus is fully rigid and gives a hard clack; the right
one is fully soft and swallows the cylinder like jelly. Same drop, same frame,
opposite result.

Imitates Kintsugi_3DCG's "0% vs 100% Torus Soft Body" format and the matching
TikTok glass-tube variant — a comparison the viewer grasps within the first
second, which is what carries the completion rate.

Both variants run simultaneously rather than as sequential stages. A staged
version would spend half the clip showing the answer the viewer already has, and
it would also route through runner.py's ``render_staged`` branch, which reads
frame math out of ``face_counts`` — a key that means nothing here.

Softness maps to the Soft Body goal: ``goal_default = 1 - softness``. A goal of 1
pins every vertex to its rest position (rigid); a goal of 0 lets the mesh flop
entirely under gravity and collision.

The dropped cylinders are keyframed with Collision modifiers rather than being
rigid bodies: Blender's soft-body solver does not interact with the rigid-body
world, so a rigid-body cylinder would pass straight through the torus.

Params:
  softness_values: list[float] (default [0.0, 1.0])   0 = rigid, 1 = fully soft
  torus_major_radius: float (default 0.8)
  torus_minor_radius: float (default 0.3)
  torus_segments: int (default 32)        major-ring resolution
  torus_rings: int (default 14)           minor-ring resolution
  column_spacing: float (default 2.2)     centre-to-centre distance between tori
  dropped_object: str (default "cylinder")  "cylinder" or "sphere"
  drop_radius: float (default 0.34)
  drop_height: float (default 1.9)
  drop_frames: int (default 26)           frames the object takes to reach the torus
  soft_body_mass: float (default 0.4)
  soft_body_friction: float (default 0.5)
  soft_body_bend: float (default 0.3)
  material_style: str (default "glass")   "glass" or "matte"
  camera_distance: float (default derived from the column spread)
  camera_height: float (default 0)
  camera_pitch_deg: float (default 66)
  camera_lens: float (default 40)
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def _soft_body_settings(obj):
    for mod in obj.modifiers:
        if mod.type == "SOFT_BODY":
            return mod.settings
    return None


def setup_scene(params: dict):
    import bpy
    from utils import clear_scene, setup_studio, setup_shorts_camera

    softness_values = params.get("softness_values", [0.0, 1.0])
    major_r = float(params.get("torus_major_radius", 0.8))
    minor_r = float(params.get("torus_minor_radius", 0.3))
    segments = int(params.get("torus_segments", 32))
    rings = int(params.get("torus_rings", 14))
    spacing = float(params.get("column_spacing", 2.2))
    drop_kind = str(params.get("dropped_object", "cylinder"))
    drop_r = float(params.get("drop_radius", 0.34))
    drop_h = float(params.get("drop_height", 1.9))
    drop_frames = int(params.get("drop_frames", 26))
    sb_mass = float(params.get("soft_body_mass", 0.4))
    sb_friction = float(params.get("soft_body_friction", 0.5))
    sb_bend = float(params.get("soft_body_bend", 0.3))
    material_style = str(params.get("material_style", "glass"))

    n = max(1, len(softness_values))
    span = (n - 1) * spacing

    clear_scene()
    setup_studio(style="soft", center=(0, 0, minor_r), scale=1.6, include_backdrop=True)
    setup_shorts_camera(
        center=(0, 0, minor_r + 0.2),
        distance=params.get("camera_distance", span * 1.4 + 4.2),
        height=params.get("camera_height", 0.0),
        pitch_deg=params.get("camera_pitch_deg", 66.0),
        lens=params.get("camera_lens", 40.0),
    )

    scene = bpy.context.scene

    # --- Ground: a Collision object, not a rigid body. Soft bodies only see
    # Collision modifiers.
    bpy.ops.mesh.primitive_plane_add(size=24, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    bpy.ops.object.modifier_add(type="COLLISION")
    ground.collision.thickness_outer = 0.02
    ground.collision.damping = 0.6

    gmat = bpy.data.materials.new("ground_mat")
    gmat.use_nodes = True
    gbsdf = gmat.node_tree.nodes["Principled BSDF"]
    gbsdf.inputs["Base Color"].default_value = (0.09, 0.09, 0.11, 1)
    gbsdf.inputs["Roughness"].default_value = 0.5
    ground.data.materials.append(gmat)

    for i, raw_softness in enumerate(softness_values):
        softness = max(0.0, min(1.0, float(raw_softness)))
        x = -span / 2 + i * spacing

        # --- Torus ---
        bpy.ops.mesh.primitive_torus_add(
            location=(x, 0, minor_r),
            major_radius=major_r,
            minor_radius=minor_r,
            major_segments=segments,
            minor_segments=rings,
        )
        torus = bpy.context.active_object
        torus.name = f"torus_{i}"
        bpy.ops.object.shade_smooth()

        bpy.ops.object.modifier_add(type="SOFT_BODY")
        sb = _soft_body_settings(torus)
        if sb is not None:
            sb.use_goal = True
            # The whole comparison lives on this one line.
            sb.goal_default = 1.0 - softness
            sb.goal_spring = 0.6
            sb.goal_friction = 0.4
            sb.mass = sb_mass
            sb.friction = sb_friction
            sb.use_edges = True
            sb.pull = 0.6
            sb.push = 0.6
            sb.bend = sb_bend
            sb.speed = 1.0
            sb.use_self_collision = True
            sb.collision_type = "AVERAGE"
            sb.step_min = 12
            sb.step_max = 60

        tmat = bpy.data.materials.new(f"torus_mat_{i}")
        tmat.use_nodes = True
        tbsdf = tmat.node_tree.nodes["Principled BSDF"]
        if material_style == "glass":
            tbsdf.inputs["Base Color"].default_value = (0.7, 0.88, 1.0, 1)
            tbsdf.inputs["Roughness"].default_value = 0.08
            for socket in ("Transmission Weight", "Transmission"):
                if socket in tbsdf.inputs:
                    tbsdf.inputs[socket].default_value = 0.7
                    break
            if "IOR" in tbsdf.inputs:
                tbsdf.inputs["IOR"].default_value = 1.45
        else:
            # Warm on the soft end, cool on the rigid end, so the pair reads at a glance.
            tbsdf.inputs["Base Color"].default_value = (
                0.2 + 0.75 * softness, 0.45, 1.0 - 0.7 * softness, 1)
            tbsdf.inputs["Roughness"].default_value = 0.3
        torus.data.materials.append(tmat)

        # --- Dropped object: keyframed + Collision, so the soft body reacts to it ---
        top_z = minor_r * 2 + drop_h
        if drop_kind == "sphere":
            bpy.ops.mesh.primitive_uv_sphere_add(radius=drop_r, location=(x, 0, top_z))
            bpy.ops.object.shade_smooth()
        else:
            bpy.ops.mesh.primitive_cylinder_add(
                radius=drop_r, depth=drop_r * 3.2, location=(x, 0, top_z))
        dropper = bpy.context.active_object
        dropper.name = f"dropper_{i}"
        bpy.ops.object.modifier_add(type="COLLISION")
        dropper.collision.thickness_outer = 0.02
        dropper.collision.damping = 0.8

        dmat = bpy.data.materials.new(f"dropper_mat_{i}")
        dmat.use_nodes = True
        dbsdf = dmat.node_tree.nodes["Principled BSDF"]
        dbsdf.inputs["Base Color"].default_value = (0.85, 0.75, 0.25, 1)
        dbsdf.inputs["Roughness"].default_value = 0.2
        dbsdf.inputs["Metallic"].default_value = 0.9
        dropper.data.materials.append(dmat)

        # Accelerating fall, then it keeps pushing down into the torus. Both
        # columns are keyframed identically — only the goal value differs.
        end_z = minor_r * 0.35
        dropper.location = (x, 0, top_z)
        dropper.keyframe_insert("location", index=2, frame=scene.frame_start)
        dropper.location = (x, 0, end_z)
        dropper.keyframe_insert("location", index=2, frame=scene.frame_start + drop_frames)
        dropper.location = (x, 0, end_z)
        dropper.keyframe_insert("location", index=2, frame=scene.frame_end)
        if dropper.animation_data and dropper.animation_data.action:
            for fcurve in dropper.animation_data.action.fcurves:
                for kp in fcurve.keyframe_points:
                    kp.interpolation = "SINE"
                    kp.easing = "EASE_IN"

    setup_scene._contact_frame = scene.frame_start + drop_frames
    setup_scene._column_count = n


def run_simulation(params: dict = None):
    import bpy

    scene = bpy.context.scene
    # Soft body caches are point caches like any other; bake_all covers every
    # modifier at once, which is what we want since there is no rigid-body world here.
    for obj in bpy.data.objects:
        for mod in obj.modifiers:
            if mod.type == "SOFT_BODY":
                mod.point_cache.frame_start = scene.frame_start
                mod.point_cache.frame_end = scene.frame_end
    bpy.ops.ptcache.bake_all(bake=True)


def collect_impact_events(min_interval: float = 0.05, max_events: int = 20) -> list:
    """One beat per column at contact — the hard clack and the soft squish."""
    import bpy

    scene = bpy.context.scene
    fps = float(scene.render.fps) or 30.0
    contact = getattr(setup_scene, "_contact_frame", scene.frame_start + 26)
    columns = getattr(setup_scene, "_column_count", 0)
    if not columns:
        columns = len([o for o in bpy.data.objects if o.name.startswith("dropper_")])
    if not columns:
        return []

    t = round(max(0.0, (contact - scene.frame_start) / fps), 3)
    # Same frame for every column by design, so stagger them by min_interval to
    # keep each hit audible in the mix.
    return [
        {"t": round(t + i * min_interval, 3), "type": "impact", "object": f"dropper_{i}"}
        for i in range(min(columns, max_events))
    ]
