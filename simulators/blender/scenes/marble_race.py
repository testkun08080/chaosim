"""
Marble Elimination Race.
A column of colored marbles is released at the top of a zig-zag switchback track
and tumbles down ramp by ramp. The track is built vertically so the whole race
reads inside a 9:16 frame, and the marbles bunch up and overtake on every corner.

Imitates the marble-race format (Jelle's Marble Runs, "Marble Elimination Race"
Shorts, Algodoo-style marble runs), which is a long-running staple of the
satisfying-physics bracket on YouTube Shorts and TikTok.

Params:
  marble_count: int (default 24)
  marble_radius: float (default 0.16)
  ramp_count: int (default 6)             number of switchback ramps
  ramp_spacing: float (default 1.35)      vertical drop between ramps
  ramp_tilt_deg: float (default 14)       slope of each ramp
  ramp_length: float (default 3.2)
  track_width: float (default 1.5)
  wall_height: float (default 0.34)       side rails that keep marbles on the ramp
  restitution: float (default 0.25)
  friction: float (default 0.35)
  camera_distance: float (default derived from the track height)
  camera_height: float (default 0)
  camera_pitch_deg: float (default 84)
  camera_lens: float (default 34)
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def _add_slab(bpy, name, location, scale, rotation_y=0.0, color=(0.1, 0.1, 0.12, 1),
              roughness=0.4, metallic=0.2):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.rotation_euler[1] = rotation_y
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.rigidbody.object_add()
    obj.rigid_body.type = "PASSIVE"
    obj.rigid_body.friction = 0.4
    obj.rigid_body.restitution = 0.1

    mat = bpy.data.materials.new(f"{name}_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    obj.data.materials.append(mat)
    return obj


def setup_scene(params: dict):
    import bpy
    import math
    import colorsys
    from utils import clear_scene, setup_studio, setup_shorts_camera

    n_marbles = int(params.get("marble_count", 24))
    marble_r = float(params.get("marble_radius", 0.16))
    n_ramps = int(params.get("ramp_count", 6))
    ramp_spacing = float(params.get("ramp_spacing", 1.35))
    tilt_deg = float(params.get("ramp_tilt_deg", 14))
    ramp_len = float(params.get("ramp_length", 3.2))
    track_w = float(params.get("track_width", 1.5))
    wall_h = float(params.get("wall_height", 0.34))
    restitution = float(params.get("restitution", 0.25))
    friction = float(params.get("friction", 0.35))

    track_height = n_ramps * ramp_spacing

    clear_scene()
    setup_studio(style="dark", center=(0, 0, track_height / 2), scale=1.6,
                 include_backdrop=True)

    # Near-level camera: the track is tall and narrow, so the 9:16 frame is filled
    # by height rather than by looking down at it.
    setup_shorts_camera(
        center=(0, 0, track_height / 2),
        distance=params.get("camera_distance", track_height * 1.25 + 2.0),
        height=params.get("camera_height", 0.0),
        pitch_deg=params.get("camera_pitch_deg", 84.0),
        lens=params.get("camera_lens", 34.0),
    )

    tilt = math.radians(tilt_deg)

    for i in range(n_ramps):
        z = track_height - i * ramp_spacing
        # Alternate the slope direction so marbles switch back at every level.
        direction = 1 if i % 2 == 0 else -1
        _add_slab(
            bpy,
            f"ramp_{i}",
            location=(0, 0, z),
            scale=(ramp_len, track_w, 0.12),
            rotation_y=direction * tilt,
            color=(0.16, 0.17, 0.2, 1),
            roughness=0.35,
            metallic=0.3,
        )
        # End stop on the downhill side, so marbles pile and spill over the edge
        # instead of shooting off the track.
        stop_x = direction * (ramp_len / 2)
        _add_slab(
            bpy,
            f"stop_{i}",
            location=(stop_x, 0, z - (ramp_len / 2) * math.sin(tilt) + wall_h / 2),
            scale=(0.12, track_w, wall_h),
            color=(0.35, 0.36, 0.4, 1),
            roughness=0.3,
            metallic=0.5,
        )
        # Side rails keep everything inside the frame.
        for side in (-1, 1):
            _add_slab(
                bpy,
                f"rail_{i}_{'p' if side > 0 else 'n'}",
                location=(0, side * track_w / 2, z + wall_h / 2),
                scale=(ramp_len, 0.08, wall_h),
                rotation_y=direction * tilt,
                color=(0.22, 0.23, 0.27, 1),
                roughness=0.3,
                metallic=0.4,
            )

    # Catch basin at the bottom — the finish line.
    _add_slab(bpy, "basin", location=(0, 0, -1.2), scale=(ramp_len + 1.0, track_w + 0.6, 0.2),
              color=(0.1, 0.1, 0.12, 1))
    for side in (-1, 1):
        _add_slab(bpy, f"basin_rail_{'p' if side > 0 else 'n'}",
                  location=(side * (ramp_len + 1.0) / 2, 0, -0.75),
                  scale=(0.15, track_w + 0.6, 0.8),
                  color=(0.2, 0.2, 0.24, 1))

    # Marbles start packed just above the top ramp so the race begins on frame 1.
    per_row = max(1, int(track_w / (marble_r * 2.4)))
    hue_step = 1.0 / max(1, n_marbles)
    for i in range(n_marbles):
        row = i // per_row
        col = i % per_row
        x = -ramp_len / 2 + 0.4 + row * marble_r * 2.3
        y = -track_w / 2 + marble_r * 1.4 + col * marble_r * 2.4
        z = track_height + 0.6 + row * marble_r * 0.4

        bpy.ops.mesh.primitive_uv_sphere_add(radius=marble_r, location=(x, y, z))
        marble = bpy.context.active_object
        marble.name = f"marble_{i:02d}"
        bpy.ops.object.shade_smooth()
        bpy.ops.rigidbody.object_add()
        marble.rigid_body.type = "ACTIVE"
        marble.rigid_body.mass = 0.05
        marble.rigid_body.restitution = restitution
        marble.rigid_body.friction = friction
        marble.rigid_body.collision_shape = "SPHERE"

        mat = bpy.data.materials.new(f"marble_mat_{i:02d}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        r, g, b = colorsys.hsv_to_rgb(i * hue_step, 0.85, 1.0)
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
        bsdf.inputs["Roughness"].default_value = 0.12
        bsdf.inputs["Metallic"].default_value = 0.35
        marble.data.materials.append(mat)


def run_simulation(params: dict = None):
    import bpy

    scene = bpy.context.scene
    if not scene.rigidbody_world:
        bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    # Many small fast spheres tunnel through thin ramps at the default substep
    # count. Raising it is cheaper than thickening every slab.
    rbw.substeps_per_frame = 10
    rbw.solver_iterations = 12
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


def collect_impact_events(min_interval: float = 0.06, max_events: int = 20) -> list:
    """Emit an event each time a marble crosses a ramp height — the corner clatter."""
    import bpy

    scene = bpy.context.scene
    fps = float(scene.render.fps) or 30.0
    depsgraph = bpy.context.evaluated_depsgraph_get()

    marbles = sorted(
        [o for o in bpy.data.objects if o.name.startswith("marble_")],
        key=lambda o: o.name,
    )
    ramps = [o for o in bpy.data.objects if o.name.startswith("ramp_")]
    if not marbles or not ramps:
        return []

    ramp_levels = sorted({round(r.location.z, 3) for r in ramps}, reverse=True)
    crossed = set()
    prev = {}
    events = []

    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        depsgraph.update()
        t = (frame - scene.frame_start) / fps
        for marble in marbles:
            z = marble.evaluated_get(depsgraph).matrix_world.translation.z
            was = prev.get(marble.name)
            if was is not None:
                for level in ramp_levels:
                    key = (marble.name, level)
                    if key in crossed:
                        continue
                    if was > level >= z:
                        crossed.add(key)
                        events.append({"t": round(t, 3), "type": "impact",
                                       "object": marble.name})
                        break
            prev[marble.name] = z

    events.sort(key=lambda e: e["t"])
    thinned = []
    for ev in events:
        if thinned and (ev["t"] - thinned[-1]["t"]) < min_interval:
            continue
        thinned.append(ev)
        if len(thinned) >= max_events:
            break
    return thinned
