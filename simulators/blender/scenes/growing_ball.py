"""
Growing Ball — it gets bigger every bounce.
A ball ricochets around a tall closed arena. Every wall contact makes it a little
larger, so the bounces get shorter and more frequent until the ball nearly fills
the box. The escalation is the whole hook: the viewer keeps watching to find out
when it stops fitting.

Imitates the ViralBalls-style "ball grows each bounce" format, which works on the
prediction loop — the viewer is always half a second ahead of the next collision.

Motion is integrated analytically rather than baked as a rigid body. A rigid body
cannot change size mid-simulation without the collision shape fighting the solver,
and a hand-rolled 2D bounce is both exactly reproducible and free to bake.

The ball moves in the XZ plane, which is the plane a 9:16 frame actually shows.

Params:
  start_radius: float (default 0.12)
  growth_rate: float (default 1.085)      radius multiplier per bounce
  max_bounces: int (default 40)           growth stops after this many contacts
  arena_width: float (default 2.6)
  arena_height: float (default 4.6)
  wall_thickness: float (default 0.12)
  initial_speed: float (default 7.5)      blender units per second
  initial_angle_deg: float (default 63)   launch direction from the +X axis
  gravity: float (default 0.0)            0 keeps it pinballing forever
  ball_color: [r, g, b] (default warm orange)
  camera_distance: float (default derived from the arena height)
  camera_height: float (default 0)
  camera_pitch_deg: float (default 90)    dead-on, so the arena reads as a rectangle
  camera_lens: float (default 40)
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def _build_wall(bpy, name, location, scale, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.append(mat)
    return obj


def setup_scene(params: dict):
    import bpy
    from utils import clear_scene, setup_studio, setup_shorts_camera

    arena_w = float(params.get("arena_width", 2.6))
    arena_h = float(params.get("arena_height", 4.6))
    wall_t = float(params.get("wall_thickness", 0.12))
    ball_color = params.get("ball_color", [1.0, 0.45, 0.1])

    clear_scene()
    setup_studio(style="dark", center=(0, 0, arena_h / 2), scale=1.5,
                 include_backdrop=True)
    # Straight-on: any downward tilt turns the arena into a trapezoid and the
    # bounce geometry stops reading.
    setup_shorts_camera(
        center=(0, 0, arena_h / 2),
        distance=params.get("camera_distance", arena_h * 1.15 + 1.2),
        height=params.get("camera_height", 0.0),
        pitch_deg=params.get("camera_pitch_deg", 90.0),
        lens=params.get("camera_lens", 40.0),
    )

    wall_mat = bpy.data.materials.new("wall_mat")
    wall_mat.use_nodes = True
    wbsdf = wall_mat.node_tree.nodes["Principled BSDF"]
    wbsdf.inputs["Base Color"].default_value = (0.1, 0.11, 0.14, 1)
    wbsdf.inputs["Roughness"].default_value = 0.28
    wbsdf.inputs["Metallic"].default_value = 0.7

    half_w, half_t = arena_w / 2, wall_t / 2
    _build_wall(bpy, "wall_left", (-half_w - half_t, 0, arena_h / 2),
                (wall_t, wall_t * 4, arena_h + wall_t * 2), wall_mat)
    _build_wall(bpy, "wall_right", (half_w + half_t, 0, arena_h / 2),
                (wall_t, wall_t * 4, arena_h + wall_t * 2), wall_mat)
    _build_wall(bpy, "wall_bottom", (0, 0, -half_t),
                (arena_w + wall_t * 2, wall_t * 4, wall_t), wall_mat)
    _build_wall(bpy, "wall_top", (0, 0, arena_h + half_t),
                (arena_w + wall_t * 2, wall_t * 4, wall_t), wall_mat)

    # Unit sphere: the animation scales it, so the mesh is built once at radius 1.
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, arena_h / 2))
    ball = bpy.context.active_object
    ball.name = "ball"
    bpy.ops.object.shade_smooth()

    bmat = bpy.data.materials.new("ball_mat")
    bmat.use_nodes = True
    bbsdf = bmat.node_tree.nodes["Principled BSDF"]
    bbsdf.inputs["Base Color"].default_value = (*ball_color, 1)
    bbsdf.inputs["Roughness"].default_value = 0.18
    bbsdf.inputs["Metallic"].default_value = 0.55
    emission = bmat.node_tree.nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*ball_color, 1)
    emission.inputs["Strength"].default_value = 1.2
    mix = bmat.node_tree.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.35
    out = bmat.node_tree.nodes["Material Output"]
    bmat.node_tree.links.new(bbsdf.outputs["BSDF"], mix.inputs[1])
    bmat.node_tree.links.new(emission.outputs["Emission"], mix.inputs[2])
    bmat.node_tree.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    ball.data.materials.append(bmat)


def run_simulation(params: dict = None):
    """Integrate the bounce and bake it straight to keyframes."""
    import bpy
    import math

    params = params or {}
    start_r = float(params.get("start_radius", 0.12))
    growth = float(params.get("growth_rate", 1.085))
    max_bounces = int(params.get("max_bounces", 40))
    arena_w = float(params.get("arena_width", 2.6))
    arena_h = float(params.get("arena_height", 4.6))
    speed = float(params.get("initial_speed", 7.5))
    angle_deg = float(params.get("initial_angle_deg", 63))
    gravity = float(params.get("gravity", 0.0))

    scene = bpy.context.scene
    fps = float(scene.render.fps) or 30.0
    dt = 1.0 / fps

    ball = bpy.data.objects.get("ball")
    if ball is None:
        return

    half_w = arena_w / 2
    r = start_r
    x, z = 0.0, arena_h * 0.5
    angle = math.radians(angle_deg)
    vx, vz = speed * math.cos(angle), speed * math.sin(angle)
    bounces = 0
    events = []

    for frame in range(scene.frame_start, scene.frame_end + 1):
        ball.location = (x, 0.0, z)
        ball.scale = (r, r, r)
        ball.keyframe_insert("location", frame=frame)
        ball.keyframe_insert("scale", frame=frame)

        vz -= gravity * dt
        x += vx * dt
        z += vz * dt

        hit = False
        # Clamp before reflecting, so a ball that has outgrown the gap cannot
        # jitter itself outside the arena.
        if x - r < -half_w:
            x = -half_w + r
            vx = abs(vx)
            hit = True
        elif x + r > half_w:
            x = half_w - r
            vx = -abs(vx)
            hit = True
        if z - r < 0.0:
            z = r
            vz = abs(vz)
            hit = True
        elif z + r > arena_h:
            z = arena_h - r
            vz = -abs(vz)
            hit = True

        if hit:
            events.append(round((frame - scene.frame_start) / fps, 3))
            if bounces < max_bounces:
                # Stop growing once the ball would no longer fit between the walls.
                if r * growth < min(half_w, arena_h / 2) * 0.95:
                    r *= growth
                bounces += 1

    # Hold the size steps crisp instead of letting Blender ease between them.
    if ball.animation_data and ball.animation_data.action:
        for fcurve in ball.animation_data.action.fcurves:
            for kp in fcurve.keyframe_points:
                kp.interpolation = "LINEAR"

    run_simulation._events = events


def collect_impact_events(min_interval: float = 0.05, max_events: int = 20) -> list:
    """Bounce times, straight from the integrator — no need to resample the bake."""
    times = getattr(run_simulation, "_events", [])
    thinned = []
    for t in times:
        if thinned and (t - thinned[-1]["t"]) < min_interval:
            continue
        thinned.append({"t": t, "type": "impact", "object": "ball"})
        if len(thinned) >= max_events:
            break
    return thinned
