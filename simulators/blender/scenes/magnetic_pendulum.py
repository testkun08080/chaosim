"""
Magnetic Chaotic Pendulum.
A pendulum bob swings above N fixed magnets arranged in a circle. Each magnet
pulls the bob toward it; which magnet it finally settles near (or whether it
keeps wandering) is extremely sensitive to the starting position — the same
"magnetic chaotic pendulum" effect sold as a desk toy (see physicsfun on
Instagram) and a classic chaos-theory demo. Rendered as a single glowing
trail plus small emissive magnet markers, matching the visual language of
double_pendulum.py.

Physics model (standard planar magnetic-pendulum approximation):
  a = -damping * v - spring * pos + sum_i( strength * (magnet_i - pos) / |magnet_i - pos|^3 )
This ignores true 3D pendulum swing and instead simulates the bob's (x, y)
position on a plane above the magnets — the same simplification used in most
magnetic-pendulum visualizations/toys.

Params:
  magnet_count: int (default 3)
  magnet_radius: float (default 1.2)      circle radius the magnets sit on
  bob_start_x: float (default 0.55)
  bob_start_y: float (default 0.25)
  bob_height: float (default 1.4)         resting height of the bob above the magnet plane
  spring: float (default 0.35)            restoring force toward center (gravity component)
  damping: float (default 0.18)           velocity damping (friction/air)
  magnet_strength: float (default 0.55)   pull strength per magnet
  duration_sec: float — read from concept top-level, not params
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def setup_scene(params: dict):
    import bpy
    import math
    from utils import clear_scene, setup_studio, setup_camera

    clear_scene()
    setup_studio(style="dark", center=(0, 0, 0), scale=1.2, include_backdrop=True)
    setup_camera(location=(0, -6, 4.2), rotation_degrees=(62, 0, 0))

    n_magnets = params.get("magnet_count", 3)
    magnet_r = params.get("magnet_radius", 1.2)

    magnet_colors = [
        (1.0, 0.15, 0.1, 1), (0.1, 0.4, 1.0, 1), (0.15, 1.0, 0.3, 1),
        (1.0, 0.8, 0.1, 1), (0.9, 0.1, 1.0, 1),
    ]

    for i in range(n_magnets):
        angle = (2 * math.pi / n_magnets) * i
        x = magnet_r * math.cos(angle)
        y = magnet_r * math.sin(angle)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.14, depth=0.1, location=(x, y, 0.05))
        magnet = bpy.context.active_object
        magnet.name = f"magnet_{i}"
        mat = bpy.data.materials.new(f"magnet_mat_{i}")
        mat.use_nodes = True
        emission = mat.node_tree.nodes.new("ShaderNodeEmission")
        emission.inputs["Color"].default_value = magnet_colors[i % len(magnet_colors)]
        emission.inputs["Strength"].default_value = 3.0
        mat.node_tree.links.new(
            emission.outputs["Emission"],
            mat.node_tree.nodes["Material Output"].inputs["Surface"],
        )
        magnet.data.materials.append(mat)

    # Base plate the magnets sit on (dark, matte, just for readability).
    bpy.ops.mesh.primitive_cylinder_add(radius=magnet_r + 0.5, depth=0.03, location=(0, 0, -0.02))
    plate = bpy.context.active_object
    plate.name = "MagnetPlate"
    mat = bpy.data.materials.new("plate_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.05, 0.05, 0.06, 1)
    bsdf.inputs["Roughness"].default_value = 0.35
    bsdf.inputs["Metallic"].default_value = 0.6
    plate.data.materials.append(mat)


def run_simulation():
    import bpy
    import math

    # NOTE: params aren't passed into run_simulation by runner.py (same
    # limitation as double_pendulum.py) — physics constants are hardcoded
    # here to sensible defaults. Wire params through if you need per-concept
    # tuning to actually take effect.
    n_magnets = 3
    magnet_r = 1.2
    bob_h = 1.4
    spring = 0.35
    damping = 0.18
    strength = 0.55
    dt = 1.0 / 60.0
    frames = bpy.context.scene.frame_end

    magnets = []
    for i in range(n_magnets):
        angle = (2 * math.pi / n_magnets) * i
        magnets.append((magnet_r * math.cos(angle), magnet_r * math.sin(angle)))

    x, y = 0.55, 0.25
    vx, vy = 0.0, 0.0
    positions = []

    for _ in range(frames):
        ax, ay = -spring * x - damping * vx, -spring * y - damping * vy
        for mx, my in magnets:
            dx, dy = mx - x, my - y
            dist = max(0.08, math.sqrt(dx * dx + dy * dy))
            pull = strength / (dist ** 3)
            ax += pull * dx
            ay += pull * dy
        vx += ax * dt
        vy += ay * dt
        x += vx * dt
        y += vy * dt
        positions.append((x, y, bob_h))

    curve_data = bpy.data.curves.new("bob_trail", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.bevel_depth = 0.012
    spline = curve_data.splines.new("NURBS")
    spline.points.add(len(positions) - 1)
    for j, pos in enumerate(positions):
        spline.points[j].co = (*pos, 1)

    trail = bpy.data.objects.new("bob_trail", curve_data)
    bpy.context.collection.objects.link(trail)

    mat = bpy.data.materials.new("trail_mat")
    mat.use_nodes = True
    emission = mat.node_tree.nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1)
    emission.inputs["Strength"].default_value = 4.0
    mat.node_tree.links.new(
        emission.outputs["Emission"],
        mat.node_tree.nodes["Material Output"].inputs["Surface"],
    )
    trail.data.materials.append(mat)

    # Animated bob (small glowing sphere) following the same path.
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.09, location=positions[0])
    bob = bpy.context.active_object
    bob.name = "bob"
    bob_mat = bpy.data.materials.new("bob_mat")
    bob_mat.use_nodes = True
    bsdf = bob_mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (1, 1, 1, 1)
    bsdf.inputs["Metallic"].default_value = 0.9
    bsdf.inputs["Roughness"].default_value = 0.1
    bob.data.materials.append(bob_mat)

    scene = bpy.context.scene
    for frame_idx, pos in enumerate(positions, start=scene.frame_start):
        bob.location = pos
        bob.keyframe_insert("location", frame=frame_idx)
