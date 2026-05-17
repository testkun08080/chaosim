"""
Sand/Granular Collapse Simulation.
Rigid body particle simulation of granular material collapsing.
Wall vanishes at frame 30, triggering an avalanche.

Params:
  particle_count: int (default 2000)
  stack_height: float (default 4.0)
  particle_radius: float (default 0.05)
  restitution: float (default 0.1)
  friction: float (default 0.8)
  color_gradient: bool (default true)
"""


def setup_scene(params: dict):
    import bpy
    import random
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
    from utils import clear_scene, set_black_background, add_area_light, setup_camera

    clear_scene()
    set_black_background()
    add_area_light(location=(3, -3, 8), energy=3000)
    setup_camera(location=(6, -6, 4), rotation_degrees=(70, 0, 45))

    n = params.get("particle_count", 2000)
    radius = params.get("particle_radius", 0.05)
    height = params.get("stack_height", 4.0)
    restitution = params.get("restitution", 0.1)
    friction = params.get("friction", 0.8)

    bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    bpy.ops.rigidbody.object_add()
    ground.rigid_body.type = "PASSIVE"

    bpy.ops.mesh.primitive_plane_add(size=height, location=(2.0, 0, height/2))
    wall = bpy.context.active_object
    wall.rotation_euler[1] = 1.5708
    wall.name = "Wall"
    bpy.ops.rigidbody.object_add()
    wall.rigid_body.type = "PASSIVE"
    wall.hide_viewport = True
    wall.keyframe_insert("hide_viewport", frame=1)
    wall.hide_viewport = True
    wall.keyframe_insert("hide_viewport", frame=29)
    wall.hide_viewport = True
    wall.keyframe_insert("hide_viewport", frame=30)

    for i in range(n):
        x = random.uniform(-1.5, 1.8)
        y = random.uniform(-1.0, 1.0)
        z = random.uniform(radius, height)

        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=(x, y, z))
        p = bpy.context.active_object
        p.name = f"sand_{i}"
        bpy.ops.rigidbody.object_add()
        p.rigid_body.mass = 0.01
        p.rigid_body.restitution = restitution
        p.rigid_body.friction = friction

        mat = bpy.data.materials.new(f"sand_mat_{i}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        t = z / height
        bsdf.inputs["Base Color"].default_value = (0.8 + 0.2*t, 0.6 * (1-t) + 0.3, 0.1, 1)
        bsdf.inputs["Roughness"].default_value = 0.9
        p.data.materials.append(mat)


def run_simulation():
    import bpy
    scene = bpy.context.scene
    if scene.rigidbody_world:
        scene.rigidbody_world.point_cache.frame_end = scene.frame_end
