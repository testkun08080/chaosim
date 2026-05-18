"""
Fluid Ink Drop Simulation.
Ink drops falling into water using Blender's FLIP fluid solver.
Creates hypnotic ink diffusion patterns.

Params:
  domain_size: float (default 2.0)
  ink_drops: int (default 3)
  viscosity: float (default 0.001)
  ink_colors: list of [r,g,b]
  drop_height: float (default 1.5)
"""


def setup_scene(params: dict):
    import bpy
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
    from utils import clear_scene, set_black_background, add_area_light, setup_camera

    clear_scene()
    set_black_background()
    add_area_light(location=(2, 2, 5), energy=2000)
    setup_camera(location=(0, -5, 3), rotation_degrees=(70, 0, 0))

    size = params.get("domain_size", 2.0)
    n_drops = params.get("ink_drops", 3)
    colors = params.get("ink_colors", [[0, 0, 1], [1, 0, 0], [0, 1, 0]])
    drop_h = params.get("drop_height", 1.5)

    bpy.ops.mesh.primitive_cube_add(size=size, location=(0, 0, 0))
    domain = bpy.context.active_object
    domain.name = "FluidDomain"
    bpy.ops.object.modifier_add(type="FLUID")
    domain.modifiers["Fluid"].fluid_type = "DOMAIN"
    domain.modifiers["Fluid"].domain_settings.domain_type = "LIQUID"
    domain.modifiers["Fluid"].domain_settings.resolution_max = 64

    bpy.ops.mesh.primitive_cube_add(size=size * 0.9, location=(0, 0, -0.5))
    water = bpy.context.active_object
    water.name = "Water"
    bpy.ops.object.modifier_add(type="FLUID")
    water.modifiers["Fluid"].fluid_type = "FLOW"
    water.modifiers["Fluid"].flow_settings.flow_type = "LIQUID"
    water.modifiers["Fluid"].flow_settings.flow_behavior = "GEOMETRY"

    for i in range(min(n_drops, len(colors))):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.08, location=(i * 0.4 - 0.4, 0, drop_h))
        drop = bpy.context.active_object
        drop.name = f"InkDrop_{i}"
        bpy.ops.object.modifier_add(type="FLUID")
        drop.modifiers["Fluid"].fluid_type = "FLOW"
        drop.modifiers["Fluid"].flow_settings.flow_type = "LIQUID"
        drop.modifiers["Fluid"].flow_settings.flow_behavior = "GEOMETRY"


def run_simulation():
    import bpy
    domain = bpy.data.objects.get("FluidDomain")
    if domain:
        bpy.ops.fluid.bake_all()
