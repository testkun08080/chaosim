"""
Funnel Vortex — coin-funnel marble drain.
Hundreds of small spheres are dropped into a wide cone. They spiral inward,
speeding up as the radius shrinks, and drain through the hole at the bottom.
The loop point is the moment the last ball disappears.

Imitates the "coin vortex" / endless-marble-run format ("Absurd Marble Run That
Never Stops"), which relies on continuous spiral motion for rewatch value.

The funnel is a ring of tilted slabs rather than a cone mesh: Blender's rigid-body
MESH collision on a cone is both slower and prone to letting fast spheres tunnel,
while flat convex slabs collide cheaply and reliably.

Params:
  ball_count: int (default 160)
  ball_radius: float (default 0.09)
  funnel_radius: float (default 2.6)      radius at the rim
  funnel_depth: float (default 2.2)       rim height above the drain
  funnel_segments: int (default 32)       slabs making up the cone wall
  drain_radius: float (default 0.45)
  spawn_spread: float (default 0.75)      fraction of the rim radius balls drop onto
  spawn_frames: int (default 40)          balls are released over this many frames
  restitution: float (default 0.15)
  friction: float (default 0.22)
  camera_distance: float (default derived from the funnel radius)
  camera_height: float (default 0)
  camera_pitch_deg: float (default 46)    steep look-down so the spiral reads
  camera_lens: float (default 38)
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def setup_scene(params: dict):
    import bpy
    import math
    import random
    import colorsys
    from utils import clear_scene, setup_studio, setup_shorts_camera

    n_balls = int(params.get("ball_count", 160))
    ball_r = float(params.get("ball_radius", 0.09))
    funnel_r = float(params.get("funnel_radius", 2.6))
    funnel_d = float(params.get("funnel_depth", 2.2))
    n_segments = int(params.get("funnel_segments", 32))
    drain_r = float(params.get("drain_radius", 0.45))
    spread = float(params.get("spawn_spread", 0.75))
    spawn_frames = int(params.get("spawn_frames", 40))
    restitution = float(params.get("restitution", 0.15))
    friction = float(params.get("friction", 0.22))

    clear_scene()
    setup_studio(style="product", center=(0, 0, funnel_d / 2), scale=1.8,
                 include_backdrop=True)

    # Looking well down into the cone is what makes the spiral legible; a near-level
    # camera would show only the rim.
    setup_shorts_camera(
        center=(0, 0, funnel_d * 0.35),
        distance=params.get("camera_distance", funnel_r * 2.6),
        height=params.get("camera_height", 0.0),
        pitch_deg=params.get("camera_pitch_deg", 46.0),
        lens=params.get("camera_lens", 38.0),
    )

    # --- Cone wall from tilted slabs ---
    slope = math.atan2(funnel_d, funnel_r - drain_r)
    wall_len = math.hypot(funnel_d, funnel_r - drain_r)
    mid_r = (funnel_r + drain_r) / 2
    seg_width = 2 * math.pi * funnel_r / n_segments * 1.3

    wall_mat = bpy.data.materials.new("funnel_mat")
    wall_mat.use_nodes = True
    bsdf = wall_mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.06, 0.07, 0.09, 1)
    bsdf.inputs["Roughness"].default_value = 0.22
    bsdf.inputs["Metallic"].default_value = 0.85

    for i in range(n_segments):
        angle = 2 * math.pi * i / n_segments
        x = mid_r * math.cos(angle)
        y = mid_r * math.sin(angle)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, funnel_d / 2))
        slab = bpy.context.active_object
        slab.name = f"funnel_{i:02d}"
        slab.scale = (wall_len, seg_width, 0.09)
        # Tilt to the cone slope, then spin into place around the axis.
        slab.rotation_euler = (0.0, math.pi / 2 - slope, 0.0)
        bpy.ops.object.transform_apply(scale=True)
        slab.rotation_euler[2] = angle
        bpy.ops.rigidbody.object_add()
        slab.rigid_body.type = "PASSIVE"
        slab.rigid_body.friction = 0.18
        slab.rigid_body.restitution = 0.1
        slab.data.materials.append(wall_mat)

    # Floor with a hole is expensive to collide against; instead the balls simply
    # fall out through the drain and off-camera, which is what the format shows.

    # --- Balls, released in waves so the spiral builds instead of dumping at once ---
    random.seed(11)
    hue_step = 1.0 / max(1, n_balls)
    for i in range(n_balls):
        angle = random.uniform(0, 2 * math.pi)
        radius = funnel_r * spread * math.sqrt(random.uniform(0.25, 1.0))
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        z = funnel_d + 0.5 + (i % max(1, spawn_frames)) * ball_r * 1.2

        bpy.ops.mesh.primitive_uv_sphere_add(radius=ball_r, location=(x, y, z))
        ball = bpy.context.active_object
        ball.name = f"ball_{i:03d}"
        bpy.ops.object.shade_smooth()
        bpy.ops.rigidbody.object_add()
        ball.rigid_body.type = "ACTIVE"
        ball.rigid_body.mass = 0.02
        ball.rigid_body.restitution = restitution
        ball.rigid_body.friction = friction
        ball.rigid_body.collision_shape = "SPHERE"

        mat = bpy.data.materials.new(f"ball_mat_{i:03d}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        r, g, b = colorsys.hsv_to_rgb((i * hue_step * 2.0) % 1.0, 0.8, 1.0)
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
        bsdf.inputs["Roughness"].default_value = 0.1
        bsdf.inputs["Metallic"].default_value = 0.3
        ball.data.materials.append(mat)


def run_simulation(params: dict = None):
    import bpy

    scene = bpy.context.scene
    if not scene.rigidbody_world:
        bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    # Small spheres accelerating down a steep wall tunnel at the default substeps.
    rbw.substeps_per_frame = 12
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
