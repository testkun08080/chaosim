"""
Branding assets — channel art and character thumbnail stills.

One scene script, two shots selected by ``params.shot``:

  - ``channel``   — sphere + triangle + square with channel name text
  - ``character`` — UV sphere with a character texture mapped (round mascot thumb)

No physics; ``run_simulation`` is a no-op. Pair with ``duration_sec: 0`` /
``params.still: true`` and a ``.png`` output (or square ``resolution``) so
``runner.py`` writes a single still instead of an MP4.

Params:
  shot: str                    "channel" | "character" (default "channel")
  channel_name: str            default "Chaos Sim"
  tagline: str                 optional subtitle under the name (channel shot)
  texture_path: str            character texture (default assets/branding/character.png)
  shape_color: [r, g, b]       solid color for geometric shapes
  accent_color: [r, g, b]      triangle / highlight color
  text_color: [r, g, b]        3D text color
  studio_style: str            setup_studio style (default "soft")
  resolution: [w, h]           consumed by runner.py
  still: bool                  consumed by runner.py
  camera_distance / camera_height / camera_pitch_deg / camera_lens
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TEXTURE = _REPO_ROOT / "assets" / "branding" / "character.png"


def _as_rgba(raw, default: list[float]) -> tuple[float, float, float, float]:
    """Normalize a YAML color list. Callers must use ``params.get("…")`` so the
    catalog AST scanner can see the key."""
    if not isinstance(raw, (list, tuple)) or len(raw) < 3:
        raw = default
    return (float(raw[0]), float(raw[1]), float(raw[2]), 1.0)


def _solid_material(name: str, color: tuple[float, float, float, float], *,
                    roughness: float = 0.35, metallic: float = 0.05):
    import bpy

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def _add_text(body: str, *, location, size: float, extrude: float, color, name: str):
    import bpy

    bpy.ops.object.text_add(location=location)
    label = bpy.context.active_object
    label.name = name
    label.data.body = body
    label.data.size = size
    label.data.align_x = "CENTER"
    label.data.align_y = "CENTER"
    label.data.extrude = extrude
    # Face the camera looking from -Y (standard Chaosim framing).
    label.rotation_euler = (math.radians(90), 0.0, 0.0)

    mat = bpy.data.materials.new(f"{name}Mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = color
        bsdf.inputs["Emission Strength"].default_value = 1.5
    label.data.materials.append(mat)
    return label


def _make_triangle(location, size: float, mat):
    """Flat equilateral triangle plate (reads as a simple △ from camera)."""
    import bpy
    import bmesh
    from mathutils import Vector

    mesh = bpy.data.meshes.new("TriangleMesh")
    obj = bpy.data.objects.new("Triangle", mesh)
    bpy.context.scene.collection.objects.link(obj)

    bm = bmesh.new()
    # Equilateral triangle in the XZ plane (camera faces -Y → sees XZ).
    r = float(size)
    verts = [
        bm.verts.new(Vector((0.0, 0.0, r))),
        bm.verts.new(Vector((-r * math.sqrt(3) / 2, 0.0, -r / 2))),
        bm.verts.new(Vector((r * math.sqrt(3) / 2, 0.0, -r / 2))),
    ]
    bm.faces.new(verts)
    # Extrude slightly so it catches light as a solid, not a card.
    result = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    extruded = [v for v in result["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=extruded, vec=Vector((0.0, -0.12, 0.0)))
    bm.to_mesh(mesh)
    bm.free()

    obj.location = location
    obj.data.materials.append(mat)
    return obj


def _build_channel_shot(params: dict) -> None:
    import bpy
    from utils import setup_camera, setup_studio

    channel_name = str(params.get("channel_name", "Chaos Sim"))
    tagline = str(params.get("tagline", "") or "")
    shape_color = _as_rgba(params.get("shape_color"), [0.55, 0.78, 0.92])
    accent_color = _as_rgba(params.get("accent_color"), [0.35, 0.72, 0.88])
    text_color = _as_rgba(params.get("text_color"), [0.12, 0.18, 0.28])
    style = str(params.get("studio_style", "soft"))

    setup_studio(style=style, center=(0, 0, 0.9), scale=1.6, include_backdrop=True)
    setup_camera(
        location=(
            0.0,
            -float(params.get("camera_distance", 7.5)),
            float(params.get("camera_height", 1.4)),
        ),
        rotation_degrees=(float(params.get("camera_pitch_deg", 78)), 0, 0),
    )
    bpy.context.scene.camera.data.lens = float(params.get("camera_lens", 50))

    sphere_mat = _solid_material("ShapeSphere", shape_color, roughness=0.28, metallic=0.15)
    tri_mat = _solid_material("ShapeTriangle", accent_color, roughness=0.32, metallic=0.1)
    square_mat = _solid_material("ShapeSquare", shape_color, roughness=0.4, metallic=0.05)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.75, location=(-1.85, 0.0, 0.85))
    sphere = bpy.context.active_object
    sphere.name = "ChannelSphere"
    bpy.ops.object.shade_smooth()
    sphere.data.materials.append(sphere_mat)

    _make_triangle(location=(0.0, 0.05, 0.95), size=0.95, mat=tri_mat)

    bpy.ops.mesh.primitive_cube_add(size=1.2, location=(1.85, 0.0, 0.7))
    square = bpy.context.active_object
    square.name = "ChannelSquare"
    square.data.materials.append(square_mat)

    _add_text(
        channel_name,
        location=(0.0, 0.35, 2.35),
        size=0.55,
        extrude=0.025,
        color=text_color,
        name="ChannelName",
    )
    if tagline:
        _add_text(
            tagline,
            location=(0.0, 0.35, 1.85),
            size=0.22,
            extrude=0.01,
            color=text_color,
            name="ChannelTagline",
        )


def _character_material(texture_path: Path):
    import bpy

    mat = bpy.data.materials.new("CharacterTex")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.55
    bsdf.inputs["Metallic"].default_value = 0.0

    # Soft white base so missing/failed loads still look like the art bg.
    bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)

    if texture_path.is_file():
        img = bpy.data.images.load(str(texture_path), check_existing=True)
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.interpolation = "Closest"
        tex.location = (-300, 200)
        links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        print(f"WARNING: character texture missing: {texture_path}")

    return mat


def _build_character_shot(params: dict) -> None:
    import bpy
    from utils import setup_camera, setup_studio

    style = str(params.get("studio_style", "soft"))
    raw_path = params.get("texture_path")
    texture_path = Path(raw_path) if raw_path else _DEFAULT_TEXTURE
    if not texture_path.is_absolute():
        texture_path = _REPO_ROOT / texture_path

    setup_studio(style=style, center=(0, 0, 1.0), scale=1.2, include_backdrop=True)
    setup_camera(
        location=(
            0.0,
            -float(params.get("camera_distance", 4.2)),
            float(params.get("camera_height", 1.05)),
        ),
        rotation_degrees=(float(params.get("camera_pitch_deg", 90)), 0, 0),
    )
    bpy.context.scene.camera.data.lens = float(params.get("camera_lens", 50))

    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0.0, 0.0, 1.0), segments=64, ring_count=32)
    ball = bpy.context.active_object
    ball.name = "CharacterSphere"
    bpy.ops.object.shade_smooth()
    # Default UV sphere puts the seam toward +X; rotate so the texture center
    # faces the camera on -Y (character drawing sits on the front hemisphere).
    ball.rotation_euler = (0.0, 0.0, math.radians(90))
    ball.data.materials.append(_character_material(texture_path))


def setup_scene(params: dict):
    from utils import clear_scene

    clear_scene()
    shot = str(params.get("shot", "channel")).strip().lower()
    if shot == "character":
        _build_character_shot(params)
    else:
        _build_channel_shot(params)


def run_simulation(params=None):
    """Stills only — nothing to bake."""
    return None
