"""Chaosim scene tools — render presets and Shorts setup from the sidebar."""

bl_info = {
    "name": "Chaosim Scene Tools",
    "author": "Chaosim",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Chaosim",
    "description": "Apply Chaosim render presets, photo studio lighting, Shorts format, and frame range",
    "category": "Render",
}

import bpy
from bpy.props import StringProperty
from bpy.types import AddonPreferences, PropertyGroup

from . import operators, panels, presets, properties


class ChaosimSceneToolsPreferences(AddonPreferences):
    bl_idname = __name__

    project_root: StringProperty(
        name="Project Root",
        description="Path to the chaosim repository (auto-detected if empty)",
        subtype="DIR_PATH",
        default="",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "project_root")
        detected = presets.default_project_root()
        layout.label(text=f"Auto-detected: {detected}", icon="INFO")


classes = (
    properties.ChaosimSceneProperties,
    *operators.classes,
    *panels.classes,
    ChaosimSceneToolsPreferences,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.chaosim_scene = bpy.props.PointerProperty(type=properties.ChaosimSceneProperties)


def unregister():
    del bpy.types.Scene.chaosim_scene
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
