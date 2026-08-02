"""
Ring Escape — a ball falls through a stack of spinning rings, each with a gap.
It only gets through a ring if the gap lines up in time. Imitates the
"Can the ball escape?" / concentric-rotating-circle format that is a proven
viral template on TikTok/Shorts (ViralBalls, BallSimulator-style tools).

Each ring is built from small cuboid segments arranged around a circle with
one arc left empty (the gap), joined into a single animated (kinematic)
passive rigid body. The ball is a normal active rigid body affected by
gravity, dropped from above the stack.

Params:
  ring_count: int (default 5)
  ring_radius: float (default 1.1)          inner radius of every ring
  ring_spacing: float (default 1.1)         vertical gap between rings
  ring_gap_deg: float (default 55)          size of the opening, in degrees
  ring_thickness: float (default 0.09)      cross-section of the ring segments
  segments_per_ring: int (default 28)       how many blocks make up the solid arc
  spin_turns: list[float]                   full turns each ring makes over the clip
                                             (default alternates +1.5 / -1.5 per ring)
  ball_radius: float (default 0.16)
  ball_start_height: float (default None)   default = just above the top ring
  ball_color: [r, g, b] (default warm red)
  camera_distance: float (default scales with the stack height)
  camera_height: float (default 0)          shifts the aim point up/down
  camera_pitch_deg: float (default 68)      90 = level, smaller looks down
  camera_lens: float (default 38)
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def setup_scene(params: dict):
    import bpy
    import math
    from utils import clear_scene, setup_studio, setup_shorts_camera

    clear_scene()
    setup_studio(style="product", center=(0, 0, 0), scale=1.4, include_backdrop=True)

    n_rings = params.get("ring_count", 5)
    ring_r = params.get("ring_radius", 1.1)
    spacing = params.get("ring_spacing", 1.1)
    gap_deg = params.get("ring_gap_deg", 55)
    thickness = params.get("ring_thickness", 0.09)
    seg_count = params.get("segments_per_ring", 28)
    ball_r = params.get("ball_radius", 0.16)
    ball_color = params.get("ball_color", [1.0, 0.2, 0.15])
    spin_turns = params.get("spin_turns", [])

    stack_height = (n_rings - 1) * spacing
    # Gate 1 rejected the previous framing: pitch 80 read as a stack of tiles rather
    # than rings, and only 4 of 5 rings fit. Default to a steeper look-down so the
    # rings read as ellipses, and pull back far enough for the whole stack plus the
    # ball's drop-in headroom.
    setup_shorts_camera(
        center=(0, 0, stack_height / 2),
        distance=params.get("camera_distance", stack_height * 1.5 + 3.0),
        height=params.get("camera_height", 0.0),
        pitch_deg=params.get("camera_pitch_deg", 68.0),
        lens=params.get("camera_lens", 38.0),
    )

    ring_colors = [
        (0.2, 0.7, 1.0, 1), (1.0, 0.3, 0.5, 1), (0.3, 1.0, 0.4, 1),
        (1.0, 0.75, 0.1, 1), (0.7, 0.3, 1.0, 1), (1.0, 1.0, 1.0, 1),
    ]

    import random
    random.seed(7)

    for i in range(n_rings):
        z = i * spacing
        gap_start_deg = random.uniform(0, 360)
        arc_deg = 360 - gap_deg
        n_solid_segs = max(6, int(seg_count * (arc_deg / 360.0)))

        seg_objs = []
        for s in range(n_solid_segs):
            frac = s / max(1, n_solid_segs - 1)
            angle_deg = gap_start_deg + gap_deg + frac * arc_deg
            angle = math.radians(angle_deg)
            x = ring_r * math.cos(angle)
            y = ring_r * math.sin(angle)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
            seg = bpy.context.active_object
            arc_step = math.radians(arc_deg / n_solid_segs)
            seg.scale = (
                thickness,
                max(thickness, ring_r * arc_step * 1.15),
                thickness,
            )
            seg.rotation_euler[2] = angle + math.pi / 2
            bpy.ops.object.transform_apply(scale=True)
            seg_objs.append(seg)

        # Join into one ring object, origin at the stack's central axis.
        bpy.ops.object.select_all(action="DESELECT")
        for seg in seg_objs:
            seg.select_set(True)
        bpy.context.view_layer.objects.active = seg_objs[0]
        bpy.ops.object.join()
        ring = bpy.context.active_object
        ring.name = f"ring_{i}"

        cursor_backup = bpy.context.scene.cursor.location.copy()
        bpy.context.scene.cursor.location = (0, 0, z)
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
        bpy.context.scene.cursor.location = cursor_backup

        mat = bpy.data.materials.new(f"ring_mat_{i}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = ring_colors[i % len(ring_colors)]
        bsdf.inputs["Roughness"].default_value = 0.25
        bsdf.inputs["Metallic"].default_value = 0.4
        ring.data.materials.append(mat)

        bpy.ops.rigidbody.object_add()
        ring.rigid_body.type = "PASSIVE"
        ring.rigid_body.kinematic = True
        ring.rigid_body.collision_shape = "MESH"

        if i < len(spin_turns):
            turn = float(spin_turns[i])
        else:
            turn = 1.5 if i % 2 == 0 else -1.5
        scene = bpy.context.scene
        ring.rotation_euler[2] = 0
        ring.keyframe_insert("rotation_euler", index=2, frame=scene.frame_start)
        ring.rotation_euler[2] = turn * 2 * math.pi
        ring.keyframe_insert("rotation_euler", index=2, frame=scene.frame_end)
        if ring.animation_data and ring.animation_data.action:
            for fcurve in ring.animation_data.action.fcurves:
                for kp in fcurve.keyframe_points:
                    kp.interpolation = "LINEAR"

    # Ground far below to catch (or visually stop) the ball after the last ring.
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, -1.5))
    ground = bpy.context.active_object
    ground.name = "Ground"
    bpy.ops.rigidbody.object_add()
    ground.rigid_body.type = "PASSIVE"

    ball_h = params.get("ball_start_height") or (stack_height + spacing * 0.8)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=ball_r, location=(0, 0, ball_h))
    ball = bpy.context.active_object
    ball.name = "ball"
    bpy.ops.rigidbody.object_add()
    ball.rigid_body.type = "ACTIVE"
    ball.rigid_body.mass = 0.3
    ball.rigid_body.restitution = 0.35
    ball.rigid_body.friction = 0.3
    ball.rigid_body.collision_shape = "SPHERE"

    mat = bpy.data.materials.new("ball_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*ball_color, 1)
    bsdf.inputs["Roughness"].default_value = 0.15
    bsdf.inputs["Metallic"].default_value = 0.7
    ball.data.materials.append(mat)


def run_simulation():
    import bpy

    scene = bpy.context.scene
    if not scene.rigidbody_world:
        bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    cache = rbw.point_cache
    cache.frame_start = scene.frame_start
    cache.frame_end = scene.frame_end
    try:
        override = bpy.context.copy()
        override["point_cache"] = cache
        with bpy.context.temp_override(**override):
            bpy.ops.ptcache.bake(bake=True)
    except Exception:
        bpy.ops.ptcache.bake_all(bake=True)


def collect_impact_events(min_interval: float = 0.05, max_events: int = 20) -> list:
    """Emit one event each time the ball drops past a ring's height.

    Gate 1 flagged that this scene had no SFX anchor at all. Ring crossings are the
    beats the format is built around, so they are what Phase 3 should hit.
    Rigid-body transforms do not update ``location``, so read the evaluated object.
    """
    import bpy

    scene = bpy.context.scene
    fps = float(scene.render.fps) or 30.0
    depsgraph = bpy.context.evaluated_depsgraph_get()

    ball = bpy.data.objects.get("ball")
    rings = sorted(
        [o for o in bpy.data.objects if o.name.startswith("ring_")],
        key=lambda o: o.location.z,
        reverse=True,
    )
    if ball is None or not rings:
        return []

    pending = [(r.name, r.location.z) for r in rings]
    events = []
    prev_z = None

    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        depsgraph.update()
        z = ball.evaluated_get(depsgraph).matrix_world.translation.z
        if prev_z is not None:
            t = (frame - scene.frame_start) / fps
            remaining = []
            for name, ring_z in pending:
                if prev_z > ring_z >= z:
                    events.append({"t": round(t, 3), "type": "impact", "object": name})
                else:
                    remaining.append((name, ring_z))
            pending = remaining
        prev_z = z

    events.sort(key=lambda e: e["t"])
    thinned = []
    for ev in events:
        if thinned and (ev["t"] - thinned[-1]["t"]) < min_interval:
            continue
        thinned.append(ev)
        if len(thinned) >= max_events:
            break
    return thinned
