"""
Double Pendulum Chaos Simulation.
Ten pendulums start from nearly identical angles. They quickly diverge,
visualizing chaos theory. Rendered as glowing colored trails.

Params:
  pendulum_count: int (default 10)
  arm1_length: float (default 1.5)
  arm2_length: float (default 1.2)
  mass1: float (default 1.0)
  mass2: float (default 0.8)
  initial_angle1_deg: float (default 120)
  initial_angle2_deg: float (default 90)
"""

import math
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))


def setup_scene(params: dict):
    import bpy
    from utils import clear_scene, setup_studio, setup_camera

    clear_scene()
    setup_studio(style="dark", center=(0, 0, 0), scale=1.0, include_backdrop=True)
    setup_camera(location=(0, -12, 0), rotation_degrees=(90, 0, 0))


def run_simulation(params: dict = None):
    import bpy
    import math

    # The integrator lives here rather than in setup_scene, so runner.py hands
    # params in via utils.call_run_simulation. Defaults match the values this
    # script used while the YAML was inert.
    params = params or {}
    n = int(params.get("pendulum_count", 10))
    L1 = float(params.get("arm1_length", 1.5))
    L2 = float(params.get("arm2_length", 1.2))
    m1 = float(params.get("mass1", 1.0))
    m2 = float(params.get("mass2", 0.8))
    angle1_deg = float(params.get("initial_angle1_deg", 120))
    angle2_deg = float(params.get("initial_angle2_deg", 90))
    g = 9.81
    dt = 1.0 / 60.0
    frames = bpy.context.scene.frame_end

    colors = [
        (1, 0, 0.2, 1), (1, 0.4, 0, 1), (1, 1, 0, 1),
        (0.2, 1, 0, 1), (0, 1, 0.8, 1), (0, 0.4, 1, 1),
        (0.4, 0, 1, 1), (1, 0, 1, 1), (1, 0.5, 0.5, 1),
        (0.5, 1, 0.5, 1),
    ]

    for i in range(n):
        angle_offset = math.radians(i * 0.05)
        th1 = math.radians(angle1_deg) + angle_offset
        th2 = math.radians(angle2_deg)
        w1, w2 = 0.0, 0.0
        positions = []

        for _ in range(frames):
            def derivs(th1, th2, w1, w2):
                d = 2 * m1 + m2 - m2 * math.cos(2 * th1 - 2 * th2)
                a1 = (
                    -g * (2 * m1 + m2) * math.sin(th1)
                    - m2 * g * math.sin(th1 - 2 * th2)
                    - 2 * math.sin(th1 - th2) * m2 * (w2**2 * L2 + w1**2 * L1 * math.cos(th1 - th2))
                ) / (L1 * d)
                a2 = (
                    2 * math.sin(th1 - th2) * (
                        w1**2 * L1 * (m1 + m2)
                        + g * (m1 + m2) * math.cos(th1)
                        + w2**2 * L2 * m2 * math.cos(th1 - th2)
                    )
                ) / (L2 * d)
                return w1, w2, a1, a2

            k1 = derivs(th1, th2, w1, w2)
            k2 = derivs(th1 + dt/2*k1[0], th2 + dt/2*k1[1], w1 + dt/2*k1[2], w2 + dt/2*k1[3])
            k3 = derivs(th1 + dt/2*k2[0], th2 + dt/2*k2[1], w1 + dt/2*k2[2], w2 + dt/2*k2[3])
            k4 = derivs(th1 + dt*k3[0], th2 + dt*k3[1], w1 + dt*k3[2], w2 + dt*k3[3])

            th1 += dt/6*(k1[0]+2*k2[0]+2*k3[0]+k4[0])
            th2 += dt/6*(k1[1]+2*k2[1]+2*k3[1]+k4[1])
            w1  += dt/6*(k1[2]+2*k2[2]+2*k3[2]+k4[2])
            w2  += dt/6*(k1[3]+2*k2[3]+2*k3[3]+k4[3])

            x2 = L1 * math.sin(th1) + L2 * math.sin(th2)
            y2 = -L1 * math.cos(th1) - L2 * math.cos(th2)
            positions.append((x2, y2, 0))

        curve_data = bpy.data.curves.new(f"trail_{i}", type="CURVE")
        curve_data.dimensions = "3D"
        curve_data.bevel_depth = 0.01
        spline = curve_data.splines.new("NURBS")
        spline.points.add(len(positions) - 1)
        for j, pos in enumerate(positions):
            spline.points[j].co = (*pos, 1)

        obj = bpy.data.objects.new(f"pendulum_{i}", curve_data)
        bpy.context.collection.objects.link(obj)

        mat = bpy.data.materials.new(f"mat_{i}")
        mat.use_nodes = True
        emission = mat.node_tree.nodes.new("ShaderNodeEmission")
        emission.inputs["Color"].default_value = colors[i % len(colors)]
        emission.inputs["Strength"].default_value = 5.0
        mat.node_tree.links.new(
            emission.outputs["Emission"],
            mat.node_tree.nodes["Material Output"].inputs["Surface"]
        )
        obj.data.materials.append(mat)
