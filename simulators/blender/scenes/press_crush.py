"""
Hydraulic Press Crush.
A heavy steel plate descends at constant speed and flattens a stack of blocks.
The stack buckles, squirts sideways and finally packs solid under the plate.

Imitates the Hydraulic Press Channel format (10.3M subscribers, 6.59B views),
which built an entire genre out of "object vs. press" with a fixed camera and a
slow, inevitable descent.

The targets are rigid bodies rather than soft bodies on purpose: soft-body bakes
do not fit the CPU-only render budget on a hosted runner, and a dense rigid stack
reads as crushing just as well at Shorts scale.

Params:
  target_count: int (default 48)          blocks in the stack
  target_size: float (default 0.3)
  stack_radius: float (default 0.9)       how wide the stack is scattered
  plate_size: float (default 3.2)
  press_speed: float (default 0.055)      blender units per frame
  press_start_height: float (default 4.2)
  press_stop_height: float (default 0.32) plate stops here, packing the debris
  hold_frames: int (default 12)           frames the plate waits before descending
  friction: float (default 0.6)
  camera_distance: float (default 8.0)
  camera_height: float (default 0)
  camera_pitch_deg: float (default 82)
  camera_lens: float (default 42)
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def setup_scene(params: dict):
    import bpy
    import math
    import random
    import colorsys
    from utils import clear_scene, setup_studio, setup_shorts_camera

    n_targets = int(params.get("target_count", 48))
    target_size = float(params.get("target_size", 0.3))
    stack_radius = float(params.get("stack_radius", 0.9))
    plate_size = float(params.get("plate_size", 3.2))
    press_speed = float(params.get("press_speed", 0.055))
    start_h = float(params.get("press_start_height", 4.2))
    stop_h = float(params.get("press_stop_height", 0.32))
    hold_frames = int(params.get("hold_frames", 12))
    friction = float(params.get("friction", 0.6))

    clear_scene()
    setup_studio(style="dark", center=(0, 0, 1.4), scale=1.5, include_backdrop=True)
    setup_shorts_camera(
        center=(0, 0, 1.4),
        distance=params.get("camera_distance", 8.0),
        height=params.get("camera_height", 0.0),
        pitch_deg=params.get("camera_pitch_deg", 82.0),
        lens=params.get("camera_lens", 42.0),
    )

    # --- Anvil ---
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.15))
    anvil = bpy.context.active_object
    anvil.name = "anvil"
    anvil.scale = (plate_size, plate_size, 0.3)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.rigidbody.object_add()
    anvil.rigid_body.type = "PASSIVE"
    anvil.rigid_body.friction = 0.9

    steel = bpy.data.materials.new("steel_mat")
    steel.use_nodes = True
    bsdf = steel.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.42, 0.44, 0.48, 1)
    bsdf.inputs["Roughness"].default_value = 0.22
    bsdf.inputs["Metallic"].default_value = 1.0
    anvil.data.materials.append(steel)

    # --- Target stack ---
    random.seed(23)
    per_layer = max(1, int((stack_radius * 2) / (target_size * 1.15)) ** 2)
    hue_step = 1.0 / max(1, n_targets)
    for i in range(n_targets):
        layer = i // max(1, per_layer)
        x = random.uniform(-stack_radius, stack_radius)
        y = random.uniform(-stack_radius, stack_radius)
        z = target_size / 2 + layer * target_size * 1.05

        bpy.ops.mesh.primitive_cube_add(size=target_size, location=(x, y, z))
        block = bpy.context.active_object
        block.name = f"target_{i:03d}"
        block.rotation_euler[2] = random.uniform(0, math.pi)
        bpy.ops.rigidbody.object_add()
        block.rigid_body.type = "ACTIVE"
        block.rigid_body.mass = 0.08
        block.rigid_body.restitution = 0.05
        block.rigid_body.friction = friction
        block.rigid_body.collision_margin = 0.002

        mat = bpy.data.materials.new(f"target_mat_{i:03d}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        r, g, b = colorsys.hsv_to_rgb((0.05 + i * hue_step * 0.5) % 1.0, 0.75, 0.95)
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
        bsdf.inputs["Roughness"].default_value = 0.35
        bsdf.inputs["Metallic"].default_value = 0.1
        block.data.materials.append(mat)

    # --- Press plate: kinematic, so it drives through the debris instead of
    # bouncing off it. Keyframed at a constant rate, which is what makes the
    # descent read as hydraulic rather than as a falling weight.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, start_h))
    plate = bpy.context.active_object
    plate.name = "press_plate"
    plate.scale = (plate_size * 0.82, plate_size * 0.82, 0.36)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.rigidbody.object_add()
    plate.rigid_body.type = "PASSIVE"
    plate.rigid_body.kinematic = True
    plate.rigid_body.friction = 0.9
    plate.data.materials.append(steel)

    scene = bpy.context.scene
    travel = max(0.0, start_h - stop_h)
    descend_frames = max(1, int(travel / max(1e-4, press_speed)))
    end_frame = scene.frame_start + hold_frames + descend_frames

    plate.location.z = start_h
    plate.keyframe_insert("location", index=2, frame=scene.frame_start)
    plate.keyframe_insert("location", index=2, frame=scene.frame_start + hold_frames)
    plate.location.z = stop_h
    plate.keyframe_insert("location", index=2, frame=end_frame)
    # Constant speed, no ease — a hydraulic ram does not accelerate.
    if plate.animation_data and plate.animation_data.action:
        for fcurve in plate.animation_data.action.fcurves:
            for kp in fcurve.keyframe_points:
                kp.interpolation = "LINEAR"

    # Ram column above the plate, so the frame reads as a press and not a floating slab.
    bpy.ops.mesh.primitive_cylinder_add(radius=0.45, depth=6.0,
                                        location=(0, 0, start_h + 3.2))
    ram = bpy.context.active_object
    ram.name = "press_ram"
    ram.data.materials.append(steel)
    ram.parent = plate
    ram.matrix_parent_inverse = plate.matrix_world.inverted()


def run_simulation(params: dict = None):
    import bpy

    scene = bpy.context.scene
    if not scene.rigidbody_world:
        bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    # A kinematic plate pushing into a dense stack needs the extra substeps or the
    # blocks squeeze through each other instead of packing.
    rbw.substeps_per_frame = 14
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


def collect_impact_events(min_interval: float = 0.08, max_events: int = 20) -> list:
    """Emit an event when a block is first squeezed sideways out of the stack."""
    import bpy

    scene = bpy.context.scene
    fps = float(scene.render.fps) or 30.0
    depsgraph = bpy.context.evaluated_depsgraph_get()

    blocks = sorted(
        [o for o in bpy.data.objects if o.name.startswith("target_")],
        key=lambda o: o.name,
    )
    if not blocks:
        return []

    start = {}
    fired = set()
    events = []
    threshold = 0.35

    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        depsgraph.update()
        t = (frame - scene.frame_start) / fps
        for block in blocks:
            pos = block.evaluated_get(depsgraph).matrix_world.translation
            if block.name not in start:
                start[block.name] = (pos.x, pos.y)
                continue
            if block.name in fired:
                continue
            sx, sy = start[block.name]
            if ((pos.x - sx) ** 2 + (pos.y - sy) ** 2) ** 0.5 > threshold:
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
