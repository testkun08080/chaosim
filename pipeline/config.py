"""Settings loading with ${ENV:default} interpolation, plus the stub-mode flag."""

import os
import re
from pathlib import Path

import yaml

SETTINGS_PATH = Path("config/settings.yaml")

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}")


def _interpolate(value):
    if isinstance(value, str):
        def repl(m):
            return os.environ.get(m.group(1), m.group(2) if m.group(2) is not None else "")
        return _ENV_RE.sub(repl, value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value


def load_settings(path: Path | None = None) -> dict:
    """Load config/settings.yaml with environment-variable interpolation."""
    path = Path(path) if path else SETTINGS_PATH
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return _interpolate(data)


def env_flag(name: str) -> bool:
    """Read a boolean environment flag.

    Only explicit truthy spellings count, so `CI=false` (a real convention —
    some toolchains set it to suppress warning-as-error behaviour) reads as off
    rather than as "some value is present, therefore true".
    """
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def stub_mode() -> bool:
    """Force all external tools (Blender/HyperFrames/VOICEVOX) into ffmpeg stubs."""
    return env_flag("CHAOSIM_STUB")
