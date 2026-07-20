"""
Lorenz Strange Attractor Visualization.
Five glowing particles trace the classic butterfly chaos attractor in 3D.

Params:
  sigma: float (default 10.0)
  rho: float (default 28.0)
  beta: float (default 2.667)
  n_trajectories: int (default 5)
  dt: float (default 0.005)
  trail_width: float (default 0.025)
  scale: float (default 0.15)
"""


def setup_scene(params: dict):
    import bpy
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
    from utils import clear_scene, setup_studio, setup_camera

    clear_scene()
    setup_studio(style="dark", center=(0, 0, 0), scale=1.2, include_backdrop=True)
    setup_camera(location=(0, -15, 5), rotation_degrees=(80, 0, 0))


def run_simulation():
    import bpy

    sigma = 10.0
    rho = 28.0
    beta = 2.667
    n = 5
    dt = 0.005
    scale = 0.15
    trail_width = 0.025

    frames = bpy.context.scene.frame_end
    steps_per_frame = 3

    colors = [
        (0.2, 0.6, 1.0, 1), (1.0, 0.3, 0.1, 1), (0.1, 1.0, 0.4, 1),
        (1.0, 0.8, 0.1, 1), (0.8, 0.1, 1.0, 1),
    ]

    for i in range(n):
        x, y, z = 0.1 + i * 0.001, 0.0, 0.0
        points = []

        for _ in range(frames * steps_per_frame):
            dx = sigma * (y - x)
            dy = x * (rho - z) - y
            dz = x * y - beta * z
            x += dx * dt
            y += dy * dt
            z += dz * dt
            points.append((x * scale, y * scale, (z - 25) * scale))

        sampled = points[::steps_per_frame]

        curve_data = bpy.data.curves.new(f"lorenz_{i}", type="CURVE")
        curve_data.dimensions = "3D"
        curve_data.bevel_depth = trail_width
        spline = curve_data.splines.new("NURBS")
        spline.points.add(len(sampled) - 1)
        for j, pt in enumerate(sampled):
            spline.points[j].co = (*pt, 1)

        obj = bpy.data.objects.new(f"lorenz_obj_{i}", curve_data)
        bpy.context.collection.objects.link(obj)

        mat = bpy.data.materials.new(f"lorenz_mat_{i}")
        mat.use_nodes = True
        emission = mat.node_tree.nodes.new("ShaderNodeEmission")
        emission.inputs["Color"].default_value = colors[i % len(colors)]
        emission.inputs["Strength"].default_value = 8.0
        mat.node_tree.links.new(
            emission.outputs["Emission"],
            mat.node_tree.nodes["Material Output"].inputs["Surface"]
        )
        obj.data.materials.append(mat)
