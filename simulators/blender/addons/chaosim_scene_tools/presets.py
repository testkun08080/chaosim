"""Load render presets from the Chaosim project config."""

from pathlib import Path

DEFAULT_PRESETS = {
    "preview": {"samples": 32, "resolution_percentage": 50, "fps": 30, "denoise": False},
    "medium": {"samples": 128, "resolution_percentage": 100, "fps": 60, "denoise": True},
    "high": {"samples": 512, "resolution_percentage": 100, "fps": 60, "denoise": True},
    "ultra": {"samples": 2048, "resolution_percentage": 100, "fps": 60, "denoise": True},
}


def addon_root() -> Path:
    return Path(__file__).resolve().parent


def default_project_root() -> Path:
    # simulators/blender/addons/chaosim_scene_tools -> repo root
    return addon_root().parents[3]


def get_project_root(preferences) -> Path:
    if preferences and preferences.project_root:
        return Path(preferences.project_root)
    return default_project_root()


def load_render_presets(preferences) -> dict:
    preset_path = get_project_root(preferences) / "config" / "render_presets.yaml"
    if not preset_path.is_file():
        return dict(DEFAULT_PRESETS)

    try:
        import yaml

        with open(preset_path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if isinstance(data, dict) and data:
            return data
    except Exception:
        pass

    return dict(DEFAULT_PRESETS)
