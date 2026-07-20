"""LookDev material switcher and parameter panel for Blender."""

bl_info = {
    "name": "LookDev Material Tool",
    "author": "Chaosim",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > LookDev",
    "description": "Switch LookDev shaders and tweak parameters from one panel",
    "category": "Material",
}

import bpy
from bpy.props import (
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    PointerProperty,
)
from bpy.types import AddonPreferences, Operator, Panel, PropertyGroup

PRESET_ITEMS = [
    ("PRINCIPLED", "Principled Metal", "Metallic PBR look"),
    ("TOON", "Toon Cel", "Cel-shaded toon material"),
    ("GLASS", "Glass", "Transparent refractive glass"),
    ("CLAY", "Clay", "Matte sculpt clay"),
    ("EMISSION", "Emission", "Glowing emissive surface"),
]

MATERIAL_NAMES = {
    "PRINCIPLED": "LookDev_Material",
    "TOON": "LookDev_Toon_Material",
    "GLASS": "LookDev_Glass_Material",
    "CLAY": "LookDev_Clay_Material",
    "EMISSION": "LookDev_Emission_Material",
}

TARGET_OBJECT_NAME = "LookDev_Sphere"

LINEART_GP_NAME = "LookDev_LineArt"
LINEART_LAYER_NAME = "Lines"
LINEART_MOD_NAME = "LineArt"
LINEART_MATERIAL_NAME = "LookDev_LineArt_Material"


def _node_by_type(nodes, node_type, index=0):
    matches = [n for n in nodes if n.type == node_type]
    if not matches:
        return None
    return matches[min(index, len(matches) - 1)]


def _set_input(node, socket_name, value):
    if node is None:
        return
    if isinstance(socket_name, int):
        if socket_name < len(node.inputs):
            node.inputs[socket_name].default_value = value
        return
    sock = node.inputs.get(socket_name)
    if sock is None:
        return
    sock.default_value = value


def _get_input(node, socket_name, fallback):
    if node is None:
        return fallback
    sock = node.inputs.get(socket_name)
    if sock is None:
        return fallback
    val = sock.default_value
    if hasattr(val, "__len__") and not isinstance(val, str):
        return tuple(val)
    return val


def _find_material(preset_id):
    return bpy.data.materials.get(MATERIAL_NAMES[preset_id])


def _target_object(context):
    props = context.scene.lookdev_tool
    obj = props.target_object
    if obj is None:
        obj = bpy.data.objects.get(TARGET_OBJECT_NAME)
    return obj


def _apply_preset_to_object(obj, preset_id):
    mat = _find_material(preset_id)
    if obj is None or mat is None:
        return None

    mesh = obj.data
    slot_index = None
    for i, slot_mat in enumerate(mesh.materials):
        if slot_mat and slot_mat.name == mat.name:
            slot_index = i
            break

    if slot_index is None:
        mesh.materials.append(mat)
        slot_index = len(mesh.materials) - 1

    obj.active_material_index = slot_index
    return mat


def _build_principled_material():
    mat = bpy.data.materials.new(MATERIAL_NAMES["PRINCIPLED"])
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    bsdf.label = "LookDevPrincipled"
    _set_input(bsdf, "Base Color", (0.72, 0.18, 0.12, 1.0))
    _set_input(bsdf, "Metallic", 0.85)
    _set_input(bsdf, "Roughness", 0.25)
    _set_input(bsdf, "Specular IOR Level", 0.5)
    if "Coat Weight" in bsdf.inputs:
        _set_input(bsdf, "Coat Weight", 0.15)
        _set_input(bsdf, "Coat Roughness", 0.08)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat


def _build_toon_material():
    mat = bpy.data.materials.new(MATERIAL_NAMES["TOON"])
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (900, 0)

    light_dir = nodes.new("ShaderNodeCombineXYZ")
    light_dir.location = (0, -80)
    light_dir.label = "LightDirection"
    _set_input(light_dir, "X", 0.55)
    _set_input(light_dir, "Y", -0.35)
    _set_input(light_dir, "Z", 0.75)

    geometry = nodes.new("ShaderNodeNewGeometry")
    geometry.location = (0, 120)

    dot = nodes.new("ShaderNodeVectorMath")
    dot.location = (220, 40)
    dot.operation = "DOT_PRODUCT"

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (440, 40)
    ramp.label = "CelRamp"
    ramp.color_ramp.interpolation = "CONSTANT"
    while len(ramp.color_ramp.elements) > 2:
        ramp.color_ramp.elements.remove(ramp.color_ramp.elements[0])
    while len(ramp.color_ramp.elements) < 3:
        ramp.color_ramp.elements.new(0.5)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.18, 0.08, 0.22, 1.0)
    ramp.color_ramp.elements[1].position = 0.42
    ramp.color_ramp.elements[1].color = (0.95, 0.55, 0.12, 1.0)
    ramp.color_ramp.elements[2].position = 1.0
    ramp.color_ramp.elements[2].color = (1.0, 0.92, 0.75, 1.0)

    toon = nodes.new("ShaderNodeBsdfToon")
    toon.location = (440, -140)
    toon.label = "ToonBSDF"
    _set_input(toon, "Color", (0.95, 0.55, 0.12, 1.0))
    if "Size" in toon.inputs:
        _set_input(toon, "Size", 0.85)
    if "Smooth" in toon.inputs:
        _set_input(toon, "Smooth", 0.05)

    layer_weight = nodes.new("ShaderNodeLayerWeight")
    layer_weight.location = (440, -320)
    layer_weight.label = "RimWeight"
    _set_input(layer_weight, "Blend", 0.35)

    rim_ramp = nodes.new("ShaderNodeValToRGB")
    rim_ramp.location = (660, -320)
    rim_ramp.label = "RimRamp"
    rim_ramp.color_ramp.interpolation = "CONSTANT"
    rim_ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    rim_ramp.color_ramp.elements[1].color = (0.25, 0.55, 0.95, 1)

    rim_mix = nodes.new("ShaderNodeMixRGB")
    rim_mix.location = (660, -80)
    rim_mix.label = "RimMix"
    rim_mix.blend_type = "ADD"
    _set_input(rim_mix, "Fac", 0.45)

    backfacing = nodes.new("ShaderNodeNewGeometry")
    backfacing.location = (440, -520)

    invert = nodes.new("ShaderNodeMath")
    invert.location = (660, -520)
    invert.operation = "SUBTRACT"
    _set_input(invert, 0, 1.0)

    outline_ramp = nodes.new("ShaderNodeValToRGB")
    outline_ramp.location = (880, -520)
    outline_ramp.label = "OutlineRamp"
    outline_ramp.color_ramp.interpolation = "CONSTANT"
    outline_ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.05, 1.0)
    outline_ramp.color_ramp.elements[1].color = (0.02, 0.02, 0.05, 0.0)

    emission = nodes.new("ShaderNodeEmission")
    emission.location = (880, 40)

    outline_mix = nodes.new("ShaderNodeMixShader")
    outline_mix.location = (1100, -120)

    links.new(geometry.outputs["Normal"], dot.inputs[0])
    links.new(light_dir.outputs["Vector"], dot.inputs[1])
    links.new(dot.outputs["Value"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], rim_mix.inputs["Color1"])
    links.new(layer_weight.outputs["Fresnel"], rim_ramp.inputs["Fac"])
    links.new(rim_ramp.outputs["Color"], rim_mix.inputs["Color2"])
    links.new(rim_mix.outputs["Color"], emission.inputs["Color"])
    links.new(backfacing.outputs["Backfacing"], invert.inputs[1])
    links.new(invert.outputs["Value"], outline_ramp.inputs["Fac"])
    links.new(outline_ramp.outputs["Color"], outline_mix.inputs[1])
    links.new(emission.outputs["Emission"], outline_mix.inputs[2])
    links.new(outline_mix.outputs["Shader"], output.inputs["Surface"])
    return mat


def _build_glass_material():
    mat = bpy.data.materials.new(MATERIAL_NAMES["GLASS"])
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    bsdf.label = "LookDevGlass"
    _set_input(bsdf, "Base Color", (0.82, 0.92, 1.0, 1.0))
    _set_input(bsdf, "Roughness", 0.05)
    _set_input(bsdf, "IOR", 1.45)
    _set_input(bsdf, "Transmission Weight", 1.0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat


def _build_clay_material():
    mat = bpy.data.materials.new(MATERIAL_NAMES["CLAY"])
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    bsdf.label = "LookDevClay"
    _set_input(bsdf, "Base Color", (0.78, 0.74, 0.70, 1.0))
    _set_input(bsdf, "Metallic", 0.0)
    _set_input(bsdf, "Roughness", 0.85)
    _set_input(bsdf, "Specular IOR Level", 0.25)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat


def _build_emission_material():
    mat = bpy.data.materials.new(MATERIAL_NAMES["EMISSION"])
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (500, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, -80)
    bsdf.label = "LookDevEmissionBase"
    _set_input(bsdf, "Base Color", (0.08, 0.08, 0.10, 1.0))
    _set_input(bsdf, "Roughness", 1.0)

    emission = nodes.new("ShaderNodeEmission")
    emission.location = (0, 120)
    emission.label = "LookDevEmission"
    _set_input(emission, "Color", (0.20, 0.75, 1.0, 1.0))
    _set_input(emission, "Strength", 8.0)

    mix = nodes.new("ShaderNodeMixShader")
    mix.location = (260, 20)
    _set_input(mix, "Fac", 0.92)

    links.new(emission.outputs["Emission"], mix.inputs[1])
    links.new(bsdf.outputs["BSDF"], mix.inputs[2])
    links.new(mix.outputs["Shader"], output.inputs["Surface"])
    return mat


BUILDERS = {
    "PRINCIPLED": _build_principled_material,
    "TOON": _build_toon_material,
    "GLASS": _build_glass_material,
    "CLAY": _build_clay_material,
    "EMISSION": _build_emission_material,
}


def ensure_lookdev_materials():
    for preset_id, builder in BUILDERS.items():
        name = MATERIAL_NAMES[preset_id]
        if bpy.data.materials.get(name) is None:
            builder()


def _read_params_from_material(preset_id, mat):
    props = {
        "base_color": (0.8, 0.8, 0.8, 1.0),
        "float_1": 0.5,
        "float_2": 0.5,
        "float_3": 0.5,
        "float_4": 0.5,
    }
    if mat is None or not mat.use_nodes:
        return props

    nodes = mat.node_tree.nodes
    if preset_id == "PRINCIPLED":
        bsdf = _node_by_type(nodes, "BSDF_PRINCIPLED")
        props["base_color"] = _get_input(bsdf, "Base Color", props["base_color"])
        props["float_1"] = _get_input(bsdf, "Metallic", 0.85)
        props["float_2"] = _get_input(bsdf, "Roughness", 0.25)
        props["float_3"] = _get_input(bsdf, "Coat Weight", 0.15)
        props["float_4"] = _get_input(bsdf, "Specular IOR Level", 0.5)
    elif preset_id == "TOON":
        toon = _node_by_type(nodes, "BSDF_TOON")
        ramp = next((n for n in nodes if n.label == "CelRamp"), None)
        rim_mix = next((n for n in nodes if n.label == "RimMix"), None)
        rim_weight = next((n for n in nodes if n.label == "RimWeight"), None)
        outline_ramp = next((n for n in nodes if n.label == "OutlineRamp"), None)
        props["base_color"] = _get_input(toon, "Color", (0.95, 0.55, 0.12, 1.0))
        if ramp and len(ramp.color_ramp.elements) > 1:
            props["float_1"] = ramp.color_ramp.elements[1].position
        props["float_2"] = _get_input(rim_mix, "Fac", 0.45)
        props["float_3"] = _get_input(rim_weight, "Blend", 0.35)
        if "Smooth" in toon.inputs:
            props["float_4"] = _get_input(toon, "Smooth", 0.05)
        elif outline_ramp:
            props["float_4"] = outline_ramp.color_ramp.elements[0].color[0]
    elif preset_id == "GLASS":
        bsdf = _node_by_type(nodes, "BSDF_PRINCIPLED")
        props["base_color"] = _get_input(bsdf, "Base Color", props["base_color"])
        props["float_1"] = _get_input(bsdf, "Roughness", 0.05)
        props["float_2"] = _get_input(bsdf, "IOR", 1.45)
        props["float_3"] = _get_input(bsdf, "Transmission Weight", 1.0)
        props["float_4"] = 0.0
    elif preset_id == "CLAY":
        bsdf = _node_by_type(nodes, "BSDF_PRINCIPLED")
        props["base_color"] = _get_input(bsdf, "Base Color", props["base_color"])
        props["float_1"] = _get_input(bsdf, "Roughness", 0.85)
        props["float_2"] = _get_input(bsdf, "Specular IOR Level", 0.25)
        props["float_3"] = 0.0
        props["float_4"] = 0.0
    elif preset_id == "EMISSION":
        emission = next((n for n in nodes if n.label == "LookDevEmission"), None)
        mix = _node_by_type(nodes, "MIX_SHADER")
        props["base_color"] = _get_input(emission, "Color", (0.2, 0.75, 1.0, 1.0))
        props["float_1"] = _get_input(emission, "Strength", 8.0)
        props["float_2"] = _get_input(mix, "Fac", 0.92)
        props["float_3"] = 0.0
        props["float_4"] = 0.0
    return props


def _write_params_to_material(preset_id, mat, props):
    if mat is None or not mat.use_nodes:
        return

    nodes = mat.node_tree.nodes
    base_color = props["base_color"]
    if len(base_color) == 3:
        base_color = (*base_color, 1.0)

    if preset_id == "PRINCIPLED":
        bsdf = _node_by_type(nodes, "BSDF_PRINCIPLED")
        _set_input(bsdf, "Base Color", base_color)
        _set_input(bsdf, "Metallic", props["float_1"])
        _set_input(bsdf, "Roughness", props["float_2"])
        _set_input(bsdf, "Coat Weight", props["float_3"])
        _set_input(bsdf, "Specular IOR Level", props["float_4"])
    elif preset_id == "TOON":
        toon = _node_by_type(nodes, "BSDF_TOON")
        ramp = next((n for n in nodes if n.label == "CelRamp"), None)
        rim_mix = next((n for n in nodes if n.label == "RimMix"), None)
        rim_weight = next((n for n in nodes if n.label == "RimWeight"), None)
        _set_input(toon, "Color", base_color)
        if ramp and len(ramp.color_ramp.elements) > 1:
            ramp.color_ramp.elements[1].color = base_color
            ramp.color_ramp.elements[1].position = props["float_1"]
        _set_input(rim_mix, "Fac", props["float_2"])
        _set_input(rim_weight, "Blend", props["float_3"])
        if "Smooth" in toon.inputs:
            _set_input(toon, "Smooth", props["float_4"])
    elif preset_id == "GLASS":
        bsdf = _node_by_type(nodes, "BSDF_PRINCIPLED")
        _set_input(bsdf, "Base Color", base_color)
        _set_input(bsdf, "Roughness", props["float_1"])
        _set_input(bsdf, "IOR", props["float_2"])
        _set_input(bsdf, "Transmission Weight", props["float_3"])
    elif preset_id == "CLAY":
        bsdf = _node_by_type(nodes, "BSDF_PRINCIPLED")
        _set_input(bsdf, "Base Color", base_color)
        _set_input(bsdf, "Roughness", props["float_1"])
        _set_input(bsdf, "Specular IOR Level", props["float_2"])
    elif preset_id == "EMISSION":
        emission = next((n for n in nodes if n.label == "LookDevEmission"), None)
        mix = _node_by_type(nodes, "MIX_SHADER")
        _set_input(emission, "Color", base_color)
        _set_input(emission, "Strength", props["float_1"])
        _set_input(mix, "Fac", props["float_2"])

    mat.diffuse_color = base_color[:3] + (1.0,)


def _sync_props_from_material(context):
    props = context.scene.lookdev_tool
    mat = _find_material(props.active_preset)
    if mat is None:
        return
    params = _read_params_from_material(props.active_preset, mat)
    props.syncing = True
    try:
        props.base_color = params["base_color"][:3]
        props.float_1 = params["float_1"]
        props.float_2 = params["float_2"]
        props.float_3 = params["float_3"]
        props.float_4 = params["float_4"]
    finally:
        props.syncing = False


def _push_props_to_material(context):
    props = context.scene.lookdev_tool
    if props.syncing:
        return
    mat = _find_material(props.active_preset)
    if mat is None:
        return
    params = {
        "base_color": (*props.base_color, 1.0),
        "float_1": props.float_1,
        "float_2": props.float_2,
        "float_3": props.float_3,
        "float_4": props.float_4,
    }
    _write_params_to_material(props.active_preset, mat, params)


def _on_preset_change(self, context):
    props = context.scene.lookdev_tool
    ensure_lookdev_materials()
    obj = _target_object(context)
    _apply_preset_to_object(obj, props.active_preset)
    _sync_props_from_material(context)


def _on_param_change(self, context):
    _push_props_to_material(context)


def _find_lineart_gp():
    obj = bpy.data.objects.get(LINEART_GP_NAME)
    if obj and obj.type == "GREASEPENCIL":
        return obj
    return None


def _ensure_lineart_material(color=(0.02, 0.02, 0.05, 1.0)):
    mat = bpy.data.materials.get(LINEART_MATERIAL_NAME)
    if mat is None:
        template = bpy.data.materials.get("Dots Stroke")
        if template and getattr(template, "is_grease_pencil", False):
            mat = template.copy()
            mat.name = LINEART_MATERIAL_NAME
        else:
            mat = bpy.data.materials.new(LINEART_MATERIAL_NAME)
            mat.use_nodes = True

    gp = getattr(mat, "grease_pencil", None)
    if gp:
        gp.color = color
        gp.show_stroke = True
        gp.show_fill = False
        gp.stroke_style = "SOLID"
    return mat


def _ensure_lineart_layer(gp_data):
    for layer in gp_data.layers:
        if layer.name == LINEART_LAYER_NAME:
            return layer
    return gp_data.layers.new(LINEART_LAYER_NAME, set_active=True)


def _get_or_create_lineart_gp():
    gp_obj = _find_lineart_gp()
    if gp_obj is not None:
        _ensure_lineart_layer(gp_obj.data)
        return gp_obj

    gp_data = bpy.data.grease_pencils.new(f"{LINEART_GP_NAME}_Data")
    _ensure_lineart_layer(gp_data)
    gp_obj = bpy.data.objects.new(LINEART_GP_NAME, gp_data)
    bpy.context.scene.collection.objects.link(gp_obj)
    return gp_obj


def _get_lineart_modifier(gp_obj):
    mod = gp_obj.modifiers.get(LINEART_MOD_NAME)
    if mod is None or mod.type != "LINEART":
        mod = gp_obj.modifiers.new(LINEART_MOD_NAME, "LINEART")
    return mod


def _save_view_state(context):
    return {
        "active": context.view_layer.objects.active,
        "selected": [obj for obj in context.view_layer.objects if obj.select_get()],
        "frame": context.scene.frame_current,
    }


def _restore_view_state(context, state):
    for obj in context.view_layer.objects:
        obj.select_set(obj in state["selected"])
    context.view_layer.objects.active = state["active"]
    context.scene.frame_set(state["frame"])


def _bake_lineart_strokes(context, gp_obj):
    if gp_obj is None:
        return False

    state = _save_view_state(context)
    scene = context.scene
    try:
        for obj in context.view_layer.objects:
            obj.select_set(False)
        gp_obj.select_set(True)
        context.view_layer.objects.active = gp_obj

        bake_frame = max(1, scene.frame_current, scene.frame_start)
        scene.frame_set(bake_frame)

        mod = _get_lineart_modifier(gp_obj)
        mod.is_baked = False
        bpy.ops.object.lineart_clear()
        bpy.ops.object.lineart_bake_strokes()
        return True
    except RuntimeError:
        return False
    finally:
        _restore_view_state(context, state)


def _set_lineart_visible(gp_obj, visible):
    if gp_obj is None:
        return
    gp_obj.hide_viewport = not visible
    gp_obj.hide_render = not visible
    for mod in gp_obj.modifiers:
        if mod.type == "LINEART":
            mod.show_viewport = visible
            mod.show_render = visible


def _sync_lineart_settings(context, rebake=False):
    props = context.scene.lookdev_tool
    target = _target_object(context)
    gp_obj = _find_lineart_gp()

    if not props.use_line_art:
        _set_lineart_visible(gp_obj, False)
        return gp_obj

    gp_obj = _get_or_create_lineart_gp()
    mat = _ensure_lineart_material((*props.line_art_color, 1.0))
    layer = _ensure_lineart_layer(gp_obj.data)

    if gp_obj.data.materials.find(mat.name) == -1:
        gp_obj.data.materials.append(mat)

    mod = _get_lineart_modifier(gp_obj)
    mod.source_type = "OBJECT"
    mod.source_object = target
    mod.use_contour = props.line_art_contour
    mod.use_crease = props.line_art_crease
    mod.use_intersection = props.line_art_intersection
    mod.use_shadow = False
    mod.radius = props.line_art_radius
    mod.opacity = props.line_art_opacity
    mod.crease_threshold = props.line_art_crease_threshold
    mod.target_layer = layer.name
    mod.target_material = mat
    mod.use_cache = True

    _set_lineart_visible(gp_obj, target is not None)
    if target and rebake:
        _bake_lineart_strokes(context, gp_obj)
    return gp_obj


def _on_lineart_toggle(self, context):
    _sync_lineart_settings(context, rebake=self.use_line_art)


def _on_lineart_param_change(self, context):
    if not self.use_line_art:
        return
    _sync_lineart_settings(context, rebake=False)


def _on_lineart_geometry_change(self, context):
    if not self.use_line_art:
        return
    _sync_lineart_settings(context, rebake=True)


def _on_target_change(self, context):
    if self.use_line_art:
        _sync_lineart_settings(context, rebake=True)


class LookDevToolProperties(PropertyGroup):
    syncing: bpy.props.BoolProperty(default=False, options={"HIDDEN"})

    target_object: PointerProperty(
        name="Target",
        type=bpy.types.Object,
        description="Object whose material will be switched",
        update=_on_target_change,
    )

    active_preset: EnumProperty(
        name="Material",
        items=PRESET_ITEMS,
        default="PRINCIPLED",
        update=_on_preset_change,
    )

    base_color: FloatVectorProperty(
        name="Base Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.72, 0.18, 0.12),
        update=_on_param_change,
    )

    float_1: FloatProperty(name="Float 1", min=0.0, max=1.0, default=0.5, update=_on_param_change)
    float_2: FloatProperty(name="Float 2", min=0.0, max=2.0, default=0.5, update=_on_param_change)
    float_3: FloatProperty(name="Float 3", min=0.0, max=1.0, default=0.5, update=_on_param_change)
    float_4: FloatProperty(name="Float 4", min=0.0, max=1.0, default=0.5, update=_on_param_change)

    use_line_art: bpy.props.BoolProperty(
        name="Line Art",
        description="Add Grease Pencil Line Art outlines around the target mesh",
        default=False,
        update=_on_lineart_toggle,
    )

    line_art_color: FloatVectorProperty(
        name="Line Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.02, 0.02, 0.05),
        update=_on_lineart_param_change,
    )

    line_art_radius: FloatProperty(
        name="Line Width",
        description="Line Art stroke radius",
        min=0.0005,
        max=0.2,
        default=0.015,
        precision=4,
        update=_on_lineart_param_change,
    )

    line_art_opacity: FloatProperty(
        name="Line Opacity",
        min=0.0,
        max=1.0,
        default=1.0,
        update=_on_lineart_param_change,
    )

    line_art_crease_threshold: FloatProperty(
        name="Crease Angle",
        description="Angle threshold for crease edge detection (radians)",
        min=0.0,
        max=3.14159,
        default=2.44346,
        update=_on_lineart_geometry_change,
    )

    line_art_contour: bpy.props.BoolProperty(
        name="Contour",
        default=True,
        update=_on_lineart_geometry_change,
    )

    line_art_crease: bpy.props.BoolProperty(
        name="Crease",
        default=True,
        update=_on_lineart_geometry_change,
    )

    line_art_intersection: bpy.props.BoolProperty(
        name="Intersection",
        default=True,
        update=_on_lineart_geometry_change,
    )


class LOOKDEV_OT_setup_materials(Operator):
    bl_idname = "lookdev.setup_materials"
    bl_label = "Setup LookDev Materials"
    bl_description = "Create or rebuild all LookDev shader presets"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        for name in MATERIAL_NAMES.values():
            mat = bpy.data.materials.get(name)
            if mat:
                bpy.data.materials.remove(mat)
        ensure_lookdev_materials()
        obj = _target_object(context)
        if obj:
            obj.data.materials.clear()
        _on_preset_change(context.scene.lookdev_tool, context)
        self.report({"INFO"}, "LookDev materials ready")
        return {"FINISHED"}


class LOOKDEV_OT_sync_from_material(Operator):
    bl_idname = "lookdev.sync_from_material"
    bl_label = "Pull From Material"
    bl_description = "Load panel values from the active preset material"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _sync_props_from_material(context)
        self.report({"INFO"}, "Parameters synced from material")
        return {"FINISHED"}


class LOOKDEV_OT_apply_to_target(Operator):
    bl_idname = "lookdev.apply_to_target"
    bl_label = "Apply To Target"
    bl_description = "Assign the selected preset to the target object"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.lookdev_tool
        ensure_lookdev_materials()
        obj = _target_object(context)
        if obj is None:
            self.report({"ERROR"}, "Target object not found")
            return {"CANCELLED"}
        _apply_preset_to_object(obj, props.active_preset)
        _push_props_to_material(context)
        self.report({"INFO"}, f"Applied {MATERIAL_NAMES[props.active_preset]}")
        return {"FINISHED"}


class LOOKDEV_OT_setup_line_art(Operator):
    bl_idname = "lookdev.setup_line_art"
    bl_label = "Setup Line Art"
    bl_description = "Create Grease Pencil Line Art object for the target mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.lookdev_tool
        target = _target_object(context)
        if target is None:
            self.report({"ERROR"}, "Target object not found")
            return {"CANCELLED"}

        props.use_line_art = True
        _sync_lineart_settings(context, rebake=True)
        self.report({"INFO"}, "Line Art setup complete")
        return {"FINISHED"}


class LOOKDEV_OT_bake_line_art(Operator):
    bl_idname = "lookdev.bake_line_art"
    bl_label = "Bake Line Art"
    bl_description = "Rebake Line Art strokes from the current target geometry"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        gp_obj = _find_lineart_gp()
        if gp_obj is None:
            self.report({"ERROR"}, "Line Art object not found. Run Setup Line Art first.")
            return {"CANCELLED"}

        if not _bake_lineart_strokes(context, gp_obj):
            self.report({"ERROR"}, "Line Art bake failed")
            return {"CANCELLED"}

        self.report({"INFO"}, "Line Art strokes baked")
        return {"FINISHED"}


class LOOKDEV_OT_remove_line_art(Operator):
    bl_idname = "lookdev.remove_line_art"
    bl_label = "Remove Line Art"
    bl_description = "Disable Line Art and hide the Grease Pencil object"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.lookdev_tool
        props.use_line_art = False
        _set_lineart_visible(_find_lineart_gp(), False)
        self.report({"INFO"}, "Line Art disabled")
        return {"FINISHED"}


class LOOKDEV_PT_panel(Panel):
    bl_label = "LookDev Material Tool"
    bl_idname = "LOOKDEV_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LookDev"

    def draw(self, context):
        layout = self.layout
        props = context.scene.lookdev_tool
        preset = props.active_preset

        layout.prop(props, "target_object")
        layout.prop(props, "active_preset")

        row = layout.row(align=True)
        row.operator("lookdev.apply_to_target", icon="CHECKMARK")
        row.operator("lookdev.sync_from_material", icon="FILE_REFRESH")

        box = layout.box()
        box.label(text="Parameters", icon="NODE_MATERIAL")
        box.prop(props, "base_color")

        labels = {
            "PRINCIPLED": ("Metallic", "Roughness", "Coat Weight", "Specular"),
            "TOON": ("Shadow Threshold", "Rim Strength", "Rim Width", "Toon Smooth"),
            "GLASS": ("Roughness", "IOR", "Transmission", None),
            "CLAY": ("Roughness", "Specular", None, None),
            "EMISSION": ("Emission Strength", "Glow Mix", None, None),
        }
        l1, l2, l3, l4 = labels[preset]
        box.prop(props, "float_1", text=l1)
        box.prop(props, "float_2", text=l2)
        if l3:
            box.prop(props, "float_3", text=l3)
        if l4:
            box.prop(props, "float_4", text=l4)

        layout.separator()
        line_box = layout.box()
        line_box.label(text="Line Art", icon="GREASEPENCIL")
        line_box.prop(props, "use_line_art")
        if props.use_line_art:
            line_box.prop(props, "line_art_color")
            line_box.prop(props, "line_art_radius")
            line_box.prop(props, "line_art_opacity")
            line_box.prop(props, "line_art_crease_threshold", text="Crease Angle")
            row = line_box.row(align=True)
            row.prop(props, "line_art_contour", toggle=True)
            row.prop(props, "line_art_crease", toggle=True)
            row.prop(props, "line_art_intersection", toggle=True)
            row = line_box.row(align=True)
            row.operator("lookdev.bake_line_art", icon="FILE_REFRESH")
            row.operator("lookdev.remove_line_art", icon="X")
        else:
            line_box.operator("lookdev.setup_line_art", icon="ADD")

        layout.separator()
        layout.operator("lookdev.setup_materials", icon="MATERIAL")


classes = (
    LookDevToolProperties,
    LOOKDEV_OT_setup_materials,
    LOOKDEV_OT_sync_from_material,
    LOOKDEV_OT_apply_to_target,
    LOOKDEV_OT_setup_line_art,
    LOOKDEV_OT_bake_line_art,
    LOOKDEV_OT_remove_line_art,
    LOOKDEV_PT_panel,
)


def _material_needs_rebuild(preset_id):
    mat = _find_material(preset_id)
    if mat is None or not mat.use_nodes:
        return True
    if preset_id == "TOON":
        nodes = mat.node_tree.nodes
        return not any(n.label == "CelRamp" for n in nodes)
    if preset_id == "EMISSION":
        nodes = mat.node_tree.nodes
        return not any(n.label == "LookDevEmission" for n in nodes)
    return False


def _can_access_blend_data() -> bool:
    try:
        _ = bpy.data.materials
    except AttributeError:
        return False
    return True


def _ensure_materials_on_register() -> None:
    if not _can_access_blend_data():
        return
    for preset_id in BUILDERS:
        if _material_needs_rebuild(preset_id):
            old = _find_material(preset_id)
            if old:
                bpy.data.materials.remove(old)
            BUILDERS[preset_id]()
    ensure_lookdev_materials()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.lookdev_tool = PointerProperty(type=LookDevToolProperties)
    _ensure_materials_on_register()


def unregister():
    del bpy.types.Scene.lookdev_tool
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
