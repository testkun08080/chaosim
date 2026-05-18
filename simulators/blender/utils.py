"""Shared utilities for Blender scene scripts. Runs inside Blender Python context."""


def clear_scene():
    import bpy
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for col in bpy.data.collections:
        bpy.data.collections.remove(col)


def set_black_background():
    import bpy
    bpy.context.scene.world.use_nodes = True
    bg = bpy.context.scene.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0, 0, 0, 1)
    bg.inputs["Strength"].default_value = 0.0


def add_area_light(location=(0, 0, 5), energy=1000, size=2.0):
    import bpy
    bpy.ops.object.light_add(type="AREA", location=location)
    light = bpy.context.active_object
    light.data.energy = energy
    light.data.size = size
    return light


def setup_camera(location=(0, -8, 3), rotation_degrees=(75, 0, 0)):
    import bpy
    import math
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.active_object
    cam.rotation_euler = [math.radians(r) for r in rotation_degrees]
    bpy.context.scene.camera = cam
    return cam
