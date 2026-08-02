"""
Pyramid Collapse.
A stacked pyramid of blocks stands still for a beat, then a wrecking sphere swings
in from the side and takes out the base. The whole structure drops into itself and
spills across the floor.

Imitates the destruction/collapse bracket of the satisfying-simulation genre — the
same appeal as a 100,000-domino run, compressed into a single structure so the
payoff lands inside a Shorts-length clip.

Params:
  layer_count: int (default 9)            layers, widest at the bottom
  block_size: float (default 0.34)
  block_gap: float (default 0.015)        spacing so blocks do not start interpenetrating
  block_mass: float (default 0.12)
  friction: float (default 0.72)
  restitution: float (default 0.02)
  trigger_frame: int (default 14)         frame the wrecker reaches the base
  wrecker_radius: float (default 0.42)
  wrecker_speed: float (default 7.0)      blender units per second
  wrecker_height: float (default 0.5)     height it strikes at
  camera_distance: float (default derived from the pyramid size)
  camera_height: float (default 0)
  camera_pitch_deg: float (default 80)
  camera_lens: float (default 40)
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def setup_scene(params: dict):
    import bpy
    import colorsys
    from utils import clear_scene, setup_studio, setup_shorts_camera

    layers = int(params.get("layer_count", 9))
    size = float(params.get("block_size", 0.34))
    gap = float(params.get("block_gap", 0.015))
    mass = float(params.get("block_mass", 0.12))
    friction = float(params.get("friction", 0.72))
    restitution = float(params.get("restitution", 0.02))
    trigger_frame = int(params.get("trigger_frame", 14))
    wrecker_r = float(params.get("wrecker_radius", 0.42))
    wrecker_speed = float(params.get("wrecker_speed", 7.0))
    wrecker_h = float(params.get("wrecker_height", 0.5))

    pitch = size + gap
    pyramid_h = layers * pitch
    base_w = layers * pitch

    clear_scene()
    setup_studio(style="product", center=(0, 0, pyramid_h / 2), scale=1.7,
                 include_backdrop=True)
    setup_shorts_camera(
        center=(0, 0, pyramid_h * 0.45),
        distance=params.get("camera_distance", max(base_w, pyramid_h) * 2.0 + 1.5),
        height=params.get("camera_height", 0.0),
        pitch_deg=params.get("camera_pitch_deg", 80.0),
        lens=params.get("camera_lens", 40.0),
    )

    scene = bpy.context.scene
    fps = float(scene.render.fps) or 30.0

    # --- Floor ---
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    bpy.ops.rigidbody.object_add()
    ground.rigid_body.type = "PASSIVE"
    ground.rigid_body.friction = 0.9

    gmat = bpy.data.materials.new("ground_mat")
    gmat.use_nodes = True
    gbsdf = gmat.node_tree.nodes["Principled BSDF"]
    gbsdf.inputs["Base Color"].default_value = (0.07, 0.07, 0.085, 1)
    gbsdf.inputs["Roughness"].default_value = 0.45
    ground.data.materials.append(gmat)

    # --- Pyramid: each layer is a square plate of blocks, one narrower per level ---
    index = 0
    for layer in range(layers):
        per_side = layers - layer
        z = size / 2 + layer * pitch
        offset = (per_side - 1) * pitch / 2
        hue = layer / max(1, layers - 1)

        mat = bpy.data.materials.new(f"block_mat_layer_{layer}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        r, g, b = colorsys.hsv_to_rgb(0.58 - 0.5 * hue, 0.75, 0.97)
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
        bsdf.inputs["Roughness"].default_value = 0.3
        bsdf.inputs["Metallic"].default_value = 0.15

        for ix in range(per_side):
            for iy in range(per_side):
                x = -offset + ix * pitch
                y = -offset + iy * pitch
                bpy.ops.mesh.primitive_cube_add(size=size, location=(x, y, z))
                block = bpy.context.active_object
                block.name = f"block_{index:04d}"
                bpy.ops.rigidbody.object_add()
                block.rigid_body.type = "ACTIVE"
                block.rigid_body.mass = mass
                block.rigid_body.friction = friction
                block.rigid_body.restitution = restitution
                block.rigid_body.collision_margin = 0.002
                # Let the stack settle instead of shivering for the first few frames.
                block.rigid_body.use_deactivation = True
                block.rigid_body.use_start_deactivated = True
                block.data.materials.append(mat)
                index += 1

    # --- Wrecker: kinematic so it ploughs through the base at a constant speed
    # instead of being stopped by the first block it meets.
    travel_per_frame = wrecker_speed / fps
    lead = max(1, trigger_frame - scene.frame_start)
    start_x = -base_w / 2 - wrecker_r - travel_per_frame * lead

    bpy.ops.mesh.primitive_uv_sphere_add(radius=wrecker_r,
                                         location=(start_x, 0, wrecker_h))
    wrecker = bpy.context.active_object
    wrecker.name = "wrecker"
    bpy.ops.object.shade_smooth()
    bpy.ops.rigidbody.object_add()
    wrecker.rigid_body.type = "PASSIVE"
    wrecker.rigid_body.kinematic = True
    wrecker.rigid_body.friction = 0.5

    wmat = bpy.data.materials.new("wrecker_mat")
    wmat.use_nodes = True
    wbsdf = wmat.node_tree.nodes["Principled BSDF"]
    wbsdf.inputs["Base Color"].default_value = (0.5, 0.52, 0.56, 1)
    wbsdf.inputs["Roughness"].default_value = 0.2
    wbsdf.inputs["Metallic"].default_value = 1.0
    wrecker.data.materials.append(wmat)

    total_frames = max(1, scene.frame_end - scene.frame_start)
    wrecker.location = (start_x, 0, wrecker_h)
    wrecker.keyframe_insert("location", index=0, frame=scene.frame_start)
    wrecker.location = (start_x + travel_per_frame * total_frames, 0, wrecker_h)
    wrecker.keyframe_insert("location", index=0, frame=scene.frame_end)
    if wrecker.animation_data and wrecker.animation_data.action:
        for fcurve in wrecker.animation_data.action.fcurves:
            for kp in fcurve.keyframe_points:
                kp.interpolation = "LINEAR"

    setup_scene._trigger_frame = trigger_frame


def run_simulation(params: dict = None):
    import bpy

    scene = bpy.context.scene
    if not scene.rigidbody_world:
        bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    # A tall stack of small boxes sinks into itself at the default substep count.
    rbw.substeps_per_frame = 12
    rbw.solver_iterations = 16
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
    """The strike, then each block as it first breaks loose from the stack."""
    import bpy

    scene = bpy.context.scene
    fps = float(scene.render.fps) or 30.0
    depsgraph = bpy.context.evaluated_depsgraph_get()

    blocks = sorted(
        [o for o in bpy.data.objects if o.name.startswith("block_")],
        key=lambda o: o.name,
    )
    if not blocks:
        return []

    trigger = getattr(setup_scene, "_trigger_frame", scene.frame_start + 14)
    events = [{
        "t": round(max(0.0, (trigger - scene.frame_start) / fps), 3),
        "type": "impact",
        "object": "wrecker",
    }]

    start = {}
    fired = set()
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        depsgraph.update()
        t = (frame - scene.frame_start) / fps
        for block in blocks:
            pos = block.evaluated_get(depsgraph).matrix_world.translation
            if block.name not in start:
                start[block.name] = (pos.x, pos.y, pos.z)
                continue
            if block.name in fired:
                continue
            sx, sy, sz = start[block.name]
            moved = ((pos.x - sx) ** 2 + (pos.y - sy) ** 2 + (pos.z - sz) ** 2) ** 0.5
            if moved > 0.2:
                fired.add(block.name)
                events.append({"t": round(t, 3), "type": "impact", "object": block.name})

    events.sort(key=lambda e: e["t"])
    thinned = []
    for ev in events:
        if thinned and (ev["t"] - thinned[-1]["t"]) < min_interval:
            continue
        thinned.append(ev)
        if len(thinned) >= max_events:
            break
    return thinned
