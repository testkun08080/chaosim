"""Operators for Chaosim scene setup and render configuration."""

import sys
from pathlib import Path

import bpy
from bpy.types import Operator

from . import presets


def _addon_preferences(context):
    try:
        return context.preferences.addons[__package__].preferences
    except KeyError:
        return None


def _import_blender_utils():
    """Load simulators/blender/utils.py (shared with headless runner scripts)."""
    blender_root = Path(__file__).resolve().parents[2]
    root_str = str(blender_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    import utils  # noqa: WPS433 — Blender addon path bootstrap

    return utils


def _apply_preset_to_scene(scene, preset: dict) -> None:
    scene.render.engine = "CYCLES"
    scene.render.resolution_percentage = preset.get("resolution_percentage", 100)
    scene.render.fps = preset.get("fps", 60)
    scene.cycles.samples = preset.get("samples", 128)
    scene.cycles.use_denoising = preset.get("denoise", True)


def _set_black_background() -> None:
    world = bpy.context.scene.world
    if world is None:
        return
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        bg.inputs["Strength"].default_value = 0.0


class CHAOSIM_OT_apply_render_preset(Operator):
    bl_idname = "chaosim.apply_render_preset"
    bl_label = "Apply Render Preset"
    bl_description = "Apply samples, FPS, and resolution from config/render_presets.yaml"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        prefs = _addon_preferences(context)
        all_presets = presets.load_render_presets(prefs)
        props = context.scene.chaosim_scene
        preset = all_presets.get(props.render_preset, all_presets.get("medium", {}))
        _apply_preset_to_scene(context.scene, preset)
        self.report({"INFO"}, f"Applied preset: {props.render_preset}")
        return {"FINISHED"}


def _set_ffmpeg_output(scene) -> None:
    try:
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "HIGH"
    except TypeError:
        # Blender 5+ background sessions may not expose FFMPEG on image_settings
        pass


class CHAOSIM_OT_apply_shorts_setup(Operator):
    bl_idname = "chaosim.apply_shorts_setup"
    bl_label = "Shorts Setup"
    bl_description = "1080x1920 vertical, Cycles, black background, apply current preset"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        scene.render.resolution_x = 1080
        scene.render.resolution_y = 1920
        _set_ffmpeg_output(scene)

        _set_black_background()

        prefs = _addon_preferences(context)
        all_presets = presets.load_render_presets(prefs)
        props = scene.chaosim_scene
        preset = all_presets.get(props.render_preset, all_presets.get("medium", {}))
        _apply_preset_to_scene(scene, preset)

        self.report({"INFO"}, "Shorts setup applied (1080x1920)")
        return {"FINISHED"}


class CHAOSIM_OT_set_frame_range(Operator):
    bl_idname = "chaosim.set_frame_range"
    bl_label = "Set Frame Range"
    bl_description = "Set frame_start=1 and frame_end from duration"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        props = scene.chaosim_scene
        fps = scene.render.fps or 60
        scene.frame_start = 1
        scene.frame_end = max(1, int(props.duration_sec * fps))
        self.report({"INFO"}, f"Frames 1–{scene.frame_end} ({props.duration_sec}s @ {fps}fps)")
        return {"FINISHED"}


class CHAOSIM_OT_apply_studio_setup(Operator):
    bl_idname = "chaosim.apply_studio_setup"
    bl_label = "Apply Studio"
    bl_description = "Build reusable product-photography lights + optional cyclorama (ChaosimStudio)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.chaosim_scene
        try:
            utils = _import_blender_utils()
            created = utils.setup_studio(
                style=props.studio_style,
                scale=props.studio_scale,
                include_backdrop=props.studio_include_backdrop,
                include_floor=props.studio_include_floor,
            )
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, f"Studio setup failed: {exc}")
            return {"CANCELLED"}

        names = ", ".join(sorted(created.keys()))
        self.report({"INFO"}, f"Studio '{props.studio_style}' ready ({names})")
        return {"FINISHED"}


class CHAOSIM_OT_clear_studio(Operator):
    bl_idname = "chaosim.clear_studio"
    bl_label = "Clear Studio"
    bl_description = "Remove ChaosimStudio collection (lights / backdrop)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            utils = _import_blender_utils()
            utils.clear_studio()
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, f"Clear studio failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, "ChaosimStudio cleared")
        return {"FINISHED"}


classes = (
    CHAOSIM_OT_apply_render_preset,
    CHAOSIM_OT_apply_shorts_setup,
    CHAOSIM_OT_set_frame_range,
    CHAOSIM_OT_apply_studio_setup,
    CHAOSIM_OT_clear_studio,
)
