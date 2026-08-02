"""
Glass Wall Shatter — sphere impact.
A sphere is launched at a glass pane. On contact the pane breaks into a radial
web of shards — rings and spokes, the way real glass actually fails — and the
crack races outward from the impact point before the shards drop and scatter.

Imitates the destruction/fracture bracket that sits at the top of the satisfying
3D simulation genre (Kawaken_3DCG shorts, "The Most Satisfying Physics
Simulations of 2025" compilations).

Deliberately does NOT use the Cell Fracture add-on: it is not enabled in a
headless Blender build, and enabling add-ons from a background script is exactly
the kind of environment dependency that fails only on CI. The shard web is built
directly from mesh data instead, which is deterministic and add-on free.

Shards are held in place as kinematic bodies and released on a timer proportional
to their distance from the impact point, so the fracture propagates outward
instead of the whole pane collapsing on one frame.

Params:
  pane_width: float (default 1.6)
  pane_height: float (default 2.4)
  pane_thickness: float (default 0.03)
  fracture_shard_count: int (default 80)   approximate; realised as rings x spokes
  projectile: str (default "sphere")       "sphere" or "cube"
  projectile_radius: float (default 0.22)
  projectile_speed: float (default 12.0)   blender units per second
  impact_point: [x, y, z] (default [0, 0, 1.2])
  shard_scatter_force: float (default 3.0) outward kick given to each shard
  crack_speed: float (default 9.0)         how fast the fracture front travels
  camera_distance: float (default 4.6)
  camera_height: float (default 0)
  camera_pitch_deg: float (default 88)
  camera_lens: float (default 40)
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def _shard_mesh(name, corners_xz, y0, y1):
    """Build one extruded quad shard. corners_xz is 4 (x, z) pairs, in order."""
    import bpy

    verts = [(x, y0, z) for x, z in corners_xz] + [(x, y1, z) for x, z in corners_xz]
    faces = [
        (0, 1, 2, 3),
        (7, 6, 5, 4),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def setup_scene(params: dict):
    import bpy
    import math
    import random
    from utils import clear_scene, setup_studio, setup_shorts_camera

    pane_w = float(params.get("pane_width", 1.6))
    pane_h = float(params.get("pane_height", 2.4))
    thickness = float(params.get("pane_thickness", 0.03))
    shard_count = int(params.get("fracture_shard_count", 80))
    projectile_kind = str(params.get("projectile", "sphere"))
    proj_r = float(params.get("projectile_radius", 0.22))
    proj_speed = float(params.get("projectile_speed", 12.0))
    impact = params.get("impact_point", [0.0, 0.0, 1.2])
    scatter = float(params.get("shard_scatter_force", 3.0))
    crack_speed = float(params.get("crack_speed", 9.0))

    clear_scene()
    setup_studio(style="dark", center=(0, 0, pane_h / 2), scale=1.5,
                 include_backdrop=True)
    setup_shorts_camera(
        center=(0, 0, pane_h * 0.55),
        distance=params.get("camera_distance", 4.6),
        height=params.get("camera_height", 0.0),
        pitch_deg=params.get("camera_pitch_deg", 88.0),
        lens=params.get("camera_lens", 40.0),
    )

    scene = bpy.context.scene
    fps = float(scene.render.fps) or 30.0
    ix, _iy, iz = float(impact[0]), float(impact[1]), float(impact[2])

    # Glass material, shared by every shard so the shader is compiled once.
    glass = bpy.data.materials.new("glass_mat")
    glass.use_nodes = True
    bsdf = glass.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.82, 0.92, 1.0, 1)
    bsdf.inputs["Roughness"].default_value = 0.05
    bsdf.inputs["Metallic"].default_value = 0.0
    for socket in ("Transmission Weight", "Transmission"):
        if socket in bsdf.inputs:
            bsdf.inputs[socket].default_value = 0.85
            break
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = 1.45

    # --- Radial shard web ---
    n_spokes = max(6, int(math.sqrt(shard_count * 1.6)))
    n_rings = max(2, round(shard_count / n_spokes))
    max_radius = math.hypot(pane_w, pane_h)

    random.seed(19)
    # Start slightly off zero so the innermost cells are quads, not degenerate
    # triangles, and so the projectile has a hole to pass through.
    radii = [0.05]
    for r in range(1, n_rings + 1):
        frac = (r / n_rings) ** 1.45          # denser shards near the impact
        radii.append(0.05 + frac * max_radius)

    angles = [2 * math.pi * s / n_spokes + random.uniform(-0.06, 0.06)
              for s in range(n_spokes)]
    angles.append(angles[0] + 2 * math.pi)

    y0, y1 = -thickness / 2, thickness / 2
    impact_frame = scene.frame_start + 10
    shard_index = 0

    for ri in range(n_rings):
        r0, r1 = radii[ri], radii[ri + 1]
        for si in range(n_spokes):
            a0, a1 = angles[si], angles[si + 1]
            corners = [
                (ix + r0 * math.cos(a0), iz + r0 * math.sin(a0)),
                (ix + r1 * math.cos(a0), iz + r1 * math.sin(a0)),
                (ix + r1 * math.cos(a1), iz + r1 * math.sin(a1)),
                (ix + r0 * math.cos(a1), iz + r0 * math.sin(a1)),
            ]
            # Drop cells whose centre falls outside the pane rectangle.
            cx = sum(c[0] for c in corners) / 4
            cz = sum(c[1] for c in corners) / 4
            if abs(cx) > pane_w / 2 or cz < 0 or cz > pane_h:
                continue

            name = f"shard_{shard_index:03d}"
            obj = bpy.data.objects.new(name, _shard_mesh(name, corners, y0, y1))
            scene.collection.objects.link(obj)
            obj.data.materials.append(glass)

            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.rigidbody.object_add()
            obj.select_set(False)
            obj.rigid_body.type = "ACTIVE"
            obj.rigid_body.collision_shape = "CONVEX_HULL"
            obj.rigid_body.mass = 0.02
            obj.rigid_body.restitution = 0.1
            obj.rigid_body.friction = 0.7

            # Held rigid until the crack front reaches this shard.
            dist = math.hypot(cx - ix, cz - iz)
            release = impact_frame + int(dist / max(0.1, crack_speed) * fps)
            obj.rigid_body.kinematic = True
            obj.keyframe_insert("rigid_body.kinematic", frame=scene.frame_start)
            obj.keyframe_insert("rigid_body.kinematic", frame=max(scene.frame_start, release - 1))
            obj.rigid_body.kinematic = False
            obj.keyframe_insert("rigid_body.kinematic", frame=release)

            # A kinematic-to-dynamic handover starts at zero velocity, so nudge the
            # shard outward over the last held frame; it inherits that as its kick.
            if dist > 1e-4 and scatter > 0:
                nudge = scatter * 0.004
                obj.location = (0.0, 0.0, 0.0)
                obj.keyframe_insert("location", frame=max(scene.frame_start, release - 2))
                obj.location = (
                    (cx - ix) / dist * nudge,
                    thickness * 0.5 + nudge,
                    (cz - iz) / dist * nudge,
                )
                obj.keyframe_insert("location", frame=release)

            shard_index += 1

    # --- Frame holding the pane, so it reads as a wall and not a floating sheet ---
    frame_mat = bpy.data.materials.new("frame_mat")
    frame_mat.use_nodes = True
    fbsdf = frame_mat.node_tree.nodes["Principled BSDF"]
    fbsdf.inputs["Base Color"].default_value = (0.06, 0.06, 0.07, 1)
    fbsdf.inputs["Roughness"].default_value = 0.4
    fbsdf.inputs["Metallic"].default_value = 0.8

    for name, loc, scl in (
        ("frame_left", (-pane_w / 2 - 0.06, 0, pane_h / 2), (0.1, 0.12, pane_h + 0.2)),
        ("frame_right", (pane_w / 2 + 0.06, 0, pane_h / 2), (0.1, 0.12, pane_h + 0.2)),
        ("frame_bottom", (0, 0, -0.06), (pane_w + 0.2, 0.12, 0.1)),
        ("frame_top", (0, 0, pane_h + 0.06), (pane_w + 0.2, 0.12, 0.1)),
    ):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        bar = bpy.context.active_object
        bar.name = name
        bar.scale = scl
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.rigidbody.object_add()
        bar.rigid_body.type = "PASSIVE"
        bar.data.materials.append(frame_mat)

    # Floor to catch the debris.
    bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 0, -0.12))
    floor = bpy.context.active_object
    floor.name = "Ground"
    bpy.ops.rigidbody.object_add()
    floor.rigid_body.type = "PASSIVE"
    floor.rigid_body.friction = 0.8

    # --- Projectile: kinematic all the way through, so it reliably punches the
    # pane instead of being stopped by the first shard it touches. A kinematic
    # passive body still pushes the active shards.
    travel_per_frame = proj_speed / fps
    lead_frames = impact_frame - scene.frame_start
    start_y = -travel_per_frame * lead_frames

    if projectile_kind == "cube":
        bpy.ops.mesh.primitive_cube_add(size=proj_r * 2, location=(ix, start_y, iz))
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=proj_r, location=(ix, start_y, iz))
        bpy.ops.object.shade_smooth()
    proj = bpy.context.active_object
    proj.name = "projectile"
    bpy.ops.rigidbody.object_add()
    proj.rigid_body.type = "PASSIVE"
    proj.rigid_body.kinematic = True
    proj.rigid_body.friction = 0.5

    proj_mat = bpy.data.materials.new("projectile_mat")
    proj_mat.use_nodes = True
    pbsdf = proj_mat.node_tree.nodes["Principled BSDF"]
    pbsdf.inputs["Base Color"].default_value = (0.75, 0.16, 0.12, 1)
    pbsdf.inputs["Roughness"].default_value = 0.25
    pbsdf.inputs["Metallic"].default_value = 0.9
    proj.data.materials.append(proj_mat)

    proj.location = (ix, start_y, iz)
    proj.keyframe_insert("location", frame=scene.frame_start)
    proj.location = (ix, start_y + travel_per_frame * (scene.frame_end - scene.frame_start), iz)
    proj.keyframe_insert("location", frame=scene.frame_end)
    if proj.animation_data and proj.animation_data.action:
        for fcurve in proj.animation_data.action.fcurves:
            for kp in fcurve.keyframe_points:
                kp.interpolation = "LINEAR"

    # Stash for collect_impact_events, which runs after the bake in a fresh call.
    setup_scene._impact_frame = impact_frame


def run_simulation(params: dict = None):
    import bpy

    scene = bpy.context.scene
    if not scene.rigidbody_world:
        bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    rbw.substeps_per_frame = 12
    rbw.solver_iterations = 14
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


def collect_impact_events(min_interval: float = 0.04, max_events: int = 20) -> list:
    """One sharp hit at contact, then the shard-fall tail as pieces start moving."""
    import bpy

    scene = bpy.context.scene
    fps = float(scene.render.fps) or 30.0
    depsgraph = bpy.context.evaluated_depsgraph_get()

    shards = sorted(
        [o for o in bpy.data.objects if o.name.startswith("shard_")],
        key=lambda o: o.name,
    )
    if not shards:
        return []

    impact_frame = getattr(setup_scene, "_impact_frame", scene.frame_start + 10)
    events = [{
        "t": round(max(0.0, (impact_frame - scene.frame_start) / fps), 3),
        "type": "impact",
        "object": "projectile",
    }]

    start = {}
    fired = set()
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        depsgraph.update()
        t = (frame - scene.frame_start) / fps
        for shard in shards:
            pos = shard.evaluated_get(depsgraph).matrix_world.translation
            if shard.name not in start:
                start[shard.name] = (pos.x, pos.y, pos.z)
                continue
            if shard.name in fired:
                continue
            sx, sy, sz = start[shard.name]
            moved = ((pos.x - sx) ** 2 + (pos.y - sy) ** 2 + (pos.z - sz) ** 2) ** 0.5
            if moved > 0.12:
                fired.add(shard.name)
                events.append({"t": round(t, 3), "type": "impact", "object": shard.name})

    events.sort(key=lambda e: e["t"])
    thinned = []
    for ev in events:
        if thinned and (ev["t"] - thinned[-1]["t"]) < min_interval:
            continue
        thinned.append(ev)
        if len(thinned) >= max_events:
            break
    return thinned
