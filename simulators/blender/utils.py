"""Shared utilities for Blender scene scripts. Runs inside Blender Python context."""

from __future__ import annotations

STUDIO_COLLECTION = "ChaosimStudio"
STUDIO_OBJECT_PREFIX = "Studio_"

# Softbox-style area lights for product / photo studio look.
_STUDIO_STYLES = {
    # Classic product shot: soft key + fill + cool rim + overhead, charcoal seamless.
    "product": {
        "world_color": (0.012, 0.012, 0.014, 1.0),
        "world_strength": 0.15,
        "backdrop_color": (0.18, 0.18, 0.20, 1.0),
        "floor_color": (0.08, 0.08, 0.09, 1.0),
        "floor_roughness": 0.45,
        "key": {"energy": 450, "size": (4.0, 3.0), "color": (1.0, 0.97, 0.93)},
        "fill": {"energy": 160, "size": (5.0, 4.0), "color": (0.92, 0.95, 1.0)},
        "rim": {"energy": 220, "size": (2.5, 1.5), "color": (0.85, 0.92, 1.0)},
        "top": {"energy": 120, "size": (6.0, 6.0), "color": (1.0, 1.0, 1.0)},
    },
    # Dark void studio — keeps Shorts contrast while still reading as lit product.
    "dark": {
        "world_color": (0.0, 0.0, 0.0, 1.0),
        "world_strength": 0.0,
        "backdrop_color": (0.02, 0.02, 0.025, 1.0),
        "floor_color": (0.03, 0.03, 0.035, 1.0),
        "floor_roughness": 0.55,
        "key": {"energy": 550, "size": (3.5, 2.5), "color": (1.0, 0.98, 0.95)},
        "fill": {"energy": 90, "size": (4.5, 3.5), "color": (0.9, 0.94, 1.0)},
        "rim": {"energy": 280, "size": (2.0, 1.2), "color": (0.8, 0.9, 1.0)},
        "top": {"energy": 80, "size": (5.0, 5.0), "color": (1.0, 1.0, 1.0)},
    },
    # Very soft even light — good for granular / fluid detail without hard shadows.
    "soft": {
        "world_color": (0.02, 0.02, 0.025, 1.0),
        "world_strength": 0.35,
        "backdrop_color": (0.22, 0.22, 0.24, 1.0),
        "floor_color": (0.12, 0.12, 0.13, 1.0),
        "floor_roughness": 0.65,
        "key": {"energy": 280, "size": (6.0, 5.0), "color": (1.0, 0.99, 0.97)},
        "fill": {"energy": 200, "size": (7.0, 6.0), "color": (0.95, 0.97, 1.0)},
        "rim": {"energy": 100, "size": (4.0, 2.5), "color": (0.9, 0.95, 1.0)},
        "top": {"energy": 180, "size": (8.0, 8.0), "color": (1.0, 1.0, 1.0)},
    },
}


def clear_scene():
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def set_black_background():
    """Legacy helper — prefer setup_studio() for production lighting."""
    import bpy

    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0, 0, 0, 1)
        bg.inputs["Strength"].default_value = 0.0


def add_area_light(
    location=(0, 0, 5),
    energy=1000,
    size=2.0,
    *,
    name=None,
    size_y=None,
    color=(1.0, 1.0, 1.0),
    look_at=None,
    collection=None,
):
    """Create a soft area light. ``size`` is X; ``size_y`` defaults to ``size``."""
    import bpy
    import mathutils

    light_data = bpy.data.lights.new(name=name or "Area", type="AREA")
    light_data.energy = energy
    light_data.shape = "RECTANGLE"
    light_data.size = float(size)
    light_data.size_y = float(size_y if size_y is not None else size)
    light_data.color = color

    light = bpy.data.objects.new(name or "Area", light_data)
    light.location = location

    link_to = collection
    if link_to is None:
        link_to = bpy.context.scene.collection
    link_to.objects.link(light)

    if look_at is not None:
        direction = mathutils.Vector(look_at) - light.location
        if direction.length > 1e-6:
            light.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    return light


def setup_camera(location=(0, -8, 3), rotation_degrees=(75, 0, 0)):
    import bpy
    import math

    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    cam.location = location
    cam.rotation_euler = [math.radians(r) for r in rotation_degrees]
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def _ensure_studio_collection():
    import bpy

    col = bpy.data.collections.get(STUDIO_COLLECTION)
    if col is None:
        col = bpy.data.collections.new(STUDIO_COLLECTION)
        bpy.context.scene.collection.children.link(col)
    return col


def clear_studio():
    """Remove a previously created ChaosimStudio collection and its objects."""
    import bpy

    col = bpy.data.collections.get(STUDIO_COLLECTION)
    if col is None:
        return

    for obj in list(col.objects):
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and getattr(data, "users", 0) == 0:
            if isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)
            elif isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)

    bpy.data.collections.remove(col)


def _set_world(color, strength: float):
    import bpy

    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = color
        bg.inputs["Strength"].default_value = strength


def _make_matte_material(name: str, color, roughness: float = 0.55):
    import bpy

    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.15
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.15
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def _add_mesh_object(name: str, mesh, location, collection):
    import bpy

    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    collection.objects.link(obj)
    return obj


def _build_cyclorama(collection, center, scale: float, style: dict):
    """Seamless floor→backdrop curve (product photography cove)."""
    import bpy
    import bmesh
    from mathutils import Vector

    c = Vector(center)
    width = 14.0 * scale
    depth = 12.0 * scale
    height = 10.0 * scale
    radius = 1.6 * scale

    bm = bmesh.new()
    # Profile in YZ: floor → quarter-circle → vertical backdrop.
    pts = []
    front_y = c.y - depth * 0.35
    back_y = c.y + depth * 0.55
    curve_y = back_y - radius
    # Floor
    for i in range(8):
        t = i / 7.0
        pts.append((0.0, front_y + (curve_y - front_y) * t, c.z))
    # Cove arc
    import math

    for i in range(1, 9):
        a = (i / 8.0) * (math.pi * 0.5)
        pts.append((0.0, curve_y + math.sin(a) * radius, c.z + (1.0 - math.cos(a)) * radius))
    # Vertical wall
    top_z = c.z + height
    wall_y = back_y
    last = pts[-1]
    for i in range(1, 6):
        t = i / 5.0
        pts.append((0.0, wall_y, last[2] + (top_z - last[2]) * t))

    # Extrude profile along X
    verts_grid = []
    x_div = 10
    for yi, (x0, y, z) in enumerate(pts):
        row = []
        for xi in range(x_div + 1):
            x = c.x - width * 0.5 + (width * xi / x_div)
            row.append(bm.verts.new((x, y, z)))
        verts_grid.append(row)
    bm.verts.ensure_lookup_table()

    for yi in range(len(pts) - 1):
        for xi in range(x_div):
            v1 = verts_grid[yi][xi]
            v2 = verts_grid[yi][xi + 1]
            v3 = verts_grid[yi + 1][xi + 1]
            v4 = verts_grid[yi + 1][xi]
            bm.faces.new((v1, v2, v3, v4))

    # Open cove: ensure normals face the subject (floor +Z, backdrop −Y).
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(f"{STUDIO_OBJECT_PREFIX}CycloramaMesh")
    bm.to_mesh(mesh)
    bm.free()

    obj = _add_mesh_object(f"{STUDIO_OBJECT_PREFIX}Cyclorama", mesh, (0, 0, 0), collection)
    mat = _make_matte_material(
        f"{STUDIO_OBJECT_PREFIX}BackdropMat",
        style["backdrop_color"],
        roughness=0.7,
    )
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    # Hide from secondary rays less important; keep as catch-light surface.
    obj.visible_camera = True
    obj.visible_shadow = True
    return obj


def _build_floor(collection, center, scale: float, style: dict):
    import bpy
    from mathutils import Vector

    c = Vector(center)
    size = 16.0 * scale
    mesh = bpy.data.meshes.new(f"{STUDIO_OBJECT_PREFIX}FloorMesh")
    # Simple plane via primitive ops avoided — build manually.
    import bmesh

    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size * 0.5)
    bm.to_mesh(mesh)
    bm.free()

    obj = _add_mesh_object(f"{STUDIO_OBJECT_PREFIX}Floor", mesh, (c.x, c.y, c.z), collection)
    mat = _make_matte_material(
        f"{STUDIO_OBJECT_PREFIX}FloorMat",
        style["floor_color"],
        roughness=style["floor_roughness"],
    )
    obj.data.materials.append(mat)
    return obj


def setup_studio(
    style: str = "product",
    center=(0.0, 0.0, 0.0),
    scale: float = 1.0,
    include_floor: bool = False,
    include_backdrop: bool = True,
    energy_scale: float = 1.0,
):
    """Build a reusable product-photography studio (lights + optional cove).

    Styles: ``product`` (default), ``dark``, ``soft``.

    Objects live in collection ``ChaosimStudio`` and can be cleared with
    ``clear_studio()``. Safe to call after ``clear_scene()``.

    Returns a dict of created objects (lights, floor, backdrop).
    """
    from mathutils import Vector

    if style not in _STUDIO_STYLES:
        raise ValueError(f"Unknown studio style '{style}'. Choose from: {sorted(_STUDIO_STYLES)}")

    cfg = _STUDIO_STYLES[style]
    clear_studio()
    col = _ensure_studio_collection()
    c = Vector(center)
    s = float(scale)
    e = float(energy_scale)

    _set_world(cfg["world_color"], cfg["world_strength"])

    created = {}

    # --- Lights (look at subject center, slightly above floor) ---
    look = (c.x, c.y, c.z + 0.6 * s)

    key_cfg = cfg["key"]
    created["key"] = add_area_light(
        location=(c.x - 3.5 * s, c.y - 4.0 * s, c.z + 4.5 * s),
        energy=key_cfg["energy"] * e,
        size=key_cfg["size"][0] * s,
        size_y=key_cfg["size"][1] * s,
        name=f"{STUDIO_OBJECT_PREFIX}Key",
        color=key_cfg["color"],
        look_at=look,
        collection=col,
    )

    fill_cfg = cfg["fill"]
    created["fill"] = add_area_light(
        location=(c.x + 4.0 * s, c.y - 3.0 * s, c.z + 3.2 * s),
        energy=fill_cfg["energy"] * e,
        size=fill_cfg["size"][0] * s,
        size_y=fill_cfg["size"][1] * s,
        name=f"{STUDIO_OBJECT_PREFIX}Fill",
        color=fill_cfg["color"],
        look_at=look,
        collection=col,
    )

    rim_cfg = cfg["rim"]
    created["rim"] = add_area_light(
        location=(c.x + 1.5 * s, c.y + 4.5 * s, c.z + 3.8 * s),
        energy=rim_cfg["energy"] * e,
        size=rim_cfg["size"][0] * s,
        size_y=rim_cfg["size"][1] * s,
        name=f"{STUDIO_OBJECT_PREFIX}Rim",
        color=rim_cfg["color"],
        look_at=look,
        collection=col,
    )

    top_cfg = cfg["top"]
    created["top"] = add_area_light(
        location=(c.x, c.y - 0.5 * s, c.z + 7.0 * s),
        energy=top_cfg["energy"] * e,
        size=top_cfg["size"][0] * s,
        size_y=top_cfg["size"][1] * s,
        name=f"{STUDIO_OBJECT_PREFIX}Top",
        color=top_cfg["color"],
        look_at=look,
        collection=col,
    )

    if include_backdrop:
        created["backdrop"] = _build_cyclorama(col, c, s, cfg)
    if include_floor:
        created["floor"] = _build_floor(col, c, s, cfg)

    return created
