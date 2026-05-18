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
    from utils import clear_scene, set_black_background, add_area_light, setup_camera

    clear_scene()
    set_black_background()
    add_area_light(location=(0, 0, 10), energy=5000, size=5.0)
    add_area_light(location=(5, -5, 5), energy=1000)
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
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.05, 0.05, 1)
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
    if scene.rigidbody_world:
        scene.rigidbody_world.point_cache.frame_end = scene.frame_end
