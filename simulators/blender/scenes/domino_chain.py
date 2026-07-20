"""
Domino Chain Reaction Simulation.
Satisfying rigid body chain reaction with colorful dominos.
Camera slowly pulls back to reveal the full chain.

Params:
  domino_count: int (default 50)
  spacing: float (default 0.35)
  domino_height: float (default 0.8)
  domino_width: float (default 0.4)
  domino_depth: float (default 0.1)
  curve_radius: float (default 0) — 0 = straight line, >0 = spiral
"""


def setup_scene(params: dict):
    import bpy
    import math
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
    from utils import clear_scene, setup_studio, setup_camera

    clear_scene()
    # Reusable product studio (key/fill/rim/top + cyclorama). Physics ground is separate.
    setup_studio(style="product", center=(0, 0, 0), scale=1.4, include_backdrop=True)
    setup_camera(location=(0, -15, 8), rotation_degrees=(65, 0, 0))

    n = params.get("domino_count", 50)
    spacing = params.get("spacing", 0.35)
    h = params.get("domino_height", 0.8)
    w = params.get("domino_width", 0.4)
    d = params.get("domino_depth", 0.1)
    curve_r = params.get("curve_radius", 0.0)

    # Ground
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    bpy.ops.rigidbody.object_add()
    ground.rigid_body.type = "PASSIVE"
    mat = bpy.data.materials.new("ground_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.08, 0.08, 0.09, 1)
    bsdf.inputs["Roughness"].default_value = 0.45
    ground.data.materials.append(mat)

    hue_step = 1.0 / n
    for i in range(n):
        if curve_r > 0:
            angle = i * spacing / curve_r
            x = curve_r * math.sin(angle)
            y = curve_r * (1 - math.cos(angle)) - curve_r
            rot_z = angle
        else:
            x = i * spacing - (n * spacing / 2)
            y = 0.0
            rot_z = 0.0

        bpy.ops.mesh.primitive_cube_add(
            size=1,
            location=(x, y, h / 2)
        )
        domino = bpy.context.active_object
        domino.scale = (d, w, h)
        domino.rotation_euler[2] = rot_z
        domino.name = f"domino_{i}"
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.rigidbody.object_add()
        domino.rigid_body.mass = 0.5
        domino.rigid_body.restitution = 0.1
        domino.rigid_body.friction = 0.8

        mat = bpy.data.materials.new(f"domino_mat_{i}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        hue = i * hue_step
        import colorsys
        r, g, b = colorsys.hsv_to_rgb(hue, 0.9, 0.95)
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
        bsdf.inputs["Roughness"].default_value = 0.3
        bsdf.inputs["Metallic"].default_value = 0.1
        domino.data.materials.append(mat)

    # Trigger: invisible push force on first domino at frame 5
    first = bpy.data.objects.get("domino_0")
    if first:
        first.rigid_body.kinematic = True
        first.keyframe_insert("rigid_body.kinematic", frame=1)
        first.location.y += 0.0
        first.keyframe_insert("location", frame=1)
        first.location.y += 0.15
        first.keyframe_insert("location", frame=6)
        first.rigid_body.kinematic = False
        first.keyframe_insert("rigid_body.kinematic", frame=7)


def run_simulation():
    import bpy
    scene = bpy.context.scene
    if not scene.rigidbody_world:
        bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    cache = rbw.point_cache
    cache.frame_start = scene.frame_start
    cache.frame_end = scene.frame_end
    # Bake so animation render has simulated rigid-body frames.
    override = bpy.context.copy()
    override["point_cache"] = cache
    try:
        with bpy.context.temp_override(**override):
            bpy.ops.ptcache.bake(bake=True)
    except Exception:
        # Older Blender / context variants — fall back to bake_all.
        bpy.ops.ptcache.bake_all(bake=True)


def collect_impact_events(min_interval: float = 0.05, max_events: int = 20) -> list:
    """Sample baked rigid-body motion and emit tip/impact times for SFX.

    Uses each ``domino_*`` object's world-space up vector (rigid-body transforms
    do not update ``rotation_euler``). Emits when tip angle first exceeds ~35°.
    Times are seconds from frame_start.
    """
    import bpy
    import math
    from mathutils import Vector

    scene = bpy.context.scene
    fps = float(scene.render.fps) or 30.0
    depsgraph = bpy.context.evaluated_depsgraph_get()
    dominos = sorted(
        [obj for obj in bpy.data.objects if obj.name.startswith("domino_")],
        key=lambda o: o.name,
    )
    if not dominos:
        return []

    tipped = set()
    events = []
    tip_angle = math.radians(35.0)
    world_up = Vector((0.0, 0.0, 1.0))

    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        depsgraph.update()
        t = (frame - scene.frame_start) / fps
        for obj in dominos:
            if obj.name in tipped:
                continue
            ev = obj.evaluated_get(depsgraph)
            local_up = ev.matrix_world.to_3x3() @ world_up
            try:
                angle = local_up.angle(world_up)
            except ValueError:
                continue
            if angle > tip_angle:
                tipped.add(obj.name)
                events.append({"t": round(t, 3), "type": "impact", "object": obj.name})

    # Thin densely clustered tips so clicks stay audible.
    events.sort(key=lambda e: e["t"])
    if len(events) >= 2 and (events[-1]["t"] - events[0]["t"]) < 1.0:
        # Physics tipped nearly together — restagger for a readable cascade.
        start = events[0]["t"]
        step = max(min_interval, 1.2 / max(1, len(events) - 1))
        events = [
            {"t": round(start + i * step, 3), "type": "impact", "object": e["object"]}
            for i, e in enumerate(events)
        ]
    thinned = []
    for ev in events:
        if thinned and (ev["t"] - thinned[-1]["t"]) < min_interval:
            continue
        thinned.append(ev)
        if len(thinned) >= max_events:
            break
    return thinned
