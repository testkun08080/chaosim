"""Sidebar panels for Chaosim scene tools."""

import bpy
from bpy.types import Panel

from . import presets


class CHAOSIM_PT_scene_tools(Panel):
    bl_label = "Chaosim Scene Tools"
    bl_idname = "CHAOSIM_PT_scene_tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Chaosim"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.chaosim_scene

        layout.prop(props, "render_preset")
        layout.operator("chaosim.apply_render_preset", icon="RENDER_ANIMATION")

        layout.separator()
        layout.operator("chaosim.apply_shorts_setup", icon="OUTLINER_OB_CAMERA")

        layout.separator()
        row = layout.row(align=True)
        row.prop(props, "duration_sec")
        row.operator("chaosim.set_frame_range", icon="TIME", text="")

        studio = layout.box()
        studio.label(text="Photo Studio", icon="LIGHT_AREA")
        studio.prop(props, "studio_style")
        studio.prop(props, "studio_scale")
        row = studio.row(align=True)
        row.prop(props, "studio_include_backdrop")
        row.prop(props, "studio_include_floor")
        row = studio.row(align=True)
        row.operator("chaosim.apply_studio_setup", icon="OUTLINER_OB_LIGHT")
        row.operator("chaosim.clear_studio", icon="TRASH", text="")

        box = layout.box()
        box.label(text="Current Render", icon="INFO")
        box.label(text=f"Resolution: {scene.render.resolution_x}x{scene.render.resolution_y}")
        box.label(text=f"FPS: {scene.render.fps}  |  Engine: {scene.render.engine}")
        if scene.render.engine == "CYCLES":
            box.label(text=f"Samples: {scene.cycles.samples}  Denoise: {scene.cycles.use_denoising}")
        box.label(text=f"Frames: {scene.frame_start} – {scene.frame_end}")


class CHAOSIM_PT_preferences_info(Panel):
    bl_label = "Project"
    bl_idname = "CHAOSIM_PT_preferences_info"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Chaosim"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        try:
            prefs = context.preferences.addons[__package__].preferences
            root = prefs.project_root or str(presets.default_project_root())
        except Exception:
            root = str(presets.default_project_root())

        layout.label(text="Project root:", icon="FILE_FOLDER")
        layout.label(text=root)
        layout.label(text="Edit in Preferences → Add-ons", icon="PREFERENCES")


classes = (
    CHAOSIM_PT_scene_tools,
    CHAOSIM_PT_preferences_info,
)
