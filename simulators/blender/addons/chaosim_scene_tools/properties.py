"""Scene-level properties exposed in the Chaosim sidebar panel."""

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from bpy.types import PropertyGroup


class ChaosimSceneProperties(PropertyGroup):
    render_preset: EnumProperty(
        name="Render Preset",
        description="Preset defined in config/render_presets.yaml",
        items=[
            ("preview", "Preview", "32 samples, 50% res — fast iteration"),
            ("medium", "Medium", "128 samples — default development"),
            ("high", "High", "512 samples — production"),
            ("ultra", "Ultra", "2048 samples — archive quality"),
        ],
        default="medium",
    )

    duration_sec: FloatProperty(
        name="Duration",
        description="Animation length in seconds (sets frame_end)",
        default=15.0,
        min=1.0,
        max=120.0,
        step=10,
        precision=1,
    )

    studio_style: EnumProperty(
        name="Studio Style",
        description="Reusable product-photography lighting + backdrop",
        items=[
            ("product", "Product", "Classic soft key/fill/rim on charcoal seamless"),
            ("dark", "Dark", "High-contrast void studio for glowing subjects"),
            ("soft", "Soft", "Very even softboxes — detail-friendly"),
        ],
        default="product",
    )

    studio_scale: FloatProperty(
        name="Studio Scale",
        description="Overall size of lights and cyclorama",
        default=1.0,
        min=0.25,
        max=5.0,
        step=10,
        precision=2,
    )

    studio_include_backdrop: BoolProperty(
        name="Cyclorama",
        description="Add seamless floor→wall backdrop",
        default=True,
    )

    studio_include_floor: BoolProperty(
        name="Floor Plane",
        description="Add a separate studio floor (skip if the sim already has Ground)",
        default=False,
    )
