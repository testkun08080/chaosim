"""Resolve BGM (local assets) and SFX (macOS system sounds) for compose."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from pipeline.ffmpeg_utils import get_duration

AUDIO_ROOT = Path("assets/audio")
CATALOG_PATH = AUDIO_ROOT / "catalog.yaml"
DEFAULT_SYSTEM_SOUNDS = Path("/System/Library/Sounds")

# Anchor names used by video templates for fixed cue timing.
_ANCHOR_ALIASES = {
    "intro_start": "intro",
    "sim_start": "sim",
    "outro_start": "outro",
}


def load_catalog(path: Path | None = None) -> dict:
    path = Path(path) if path else CATALOG_PATH
    if not path.exists():
        return {
            "system_sounds_dir": str(DEFAULT_SYSTEM_SOUNDS),
            "bgm": {},
            "sfx_roles": {
                "whoosh": "Submarine",
                "intro": "Submarine",
                "impact": "Glass",
                "click": "Tink",
                "sting": "Hero",
                "outro": "Hero",
            },
        }
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def system_sounds_dir(settings: dict | None = None, catalog: dict | None = None) -> Path:
    catalog = catalog or load_catalog()
    if settings:
        custom = settings.get("compositing", {}).get("system_sounds_dir")
        if custom:
            return Path(custom)
    return Path(catalog.get("system_sounds_dir") or DEFAULT_SYSTEM_SOUNDS)


def resolve_bgm(concept: dict, video_template: dict | None = None,
                settings: dict | None = None) -> Path | None:
    """Pick a BGM file: explicit path -> music_mood match -> template default."""
    video_template = video_template or {}
    catalog = load_catalog()
    bgm_map = catalog.get("bgm") or {}

    explicit = concept.get("bgm")
    if explicit and not isinstance(explicit, dict):
        p = Path(str(explicit))
        if p.exists():
            return p

    mood = str(concept.get("music_mood") or "").lower()
    tmpl_bgm = video_template.get("bgm") or {}
    default_mood = str(tmpl_bgm.get("mood_default") or "ambient").lower()

    # Match any keyword from catalog keys inside the mood string.
    for key, rel in bgm_map.items():
        if key.lower() in mood:
            candidate = AUDIO_ROOT / rel
            if candidate.exists():
                return candidate

    for key in (default_mood, "ambient"):
        rel = bgm_map.get(key)
        if rel:
            candidate = AUDIO_ROOT / rel
            if candidate.exists():
                return candidate
    return None


def resolve_sfx_path(sound_name: str, settings: dict | None = None,
                     catalog: dict | None = None) -> Path | None:
    """Resolve a role (click) or Apple sound stem (Tink) to an .aiff path."""
    if not sound_name:
        return None
    catalog = catalog or load_catalog()
    roles = catalog.get("sfx_roles") or {}
    stem = roles.get(sound_name) or roles.get(sound_name.lower()) or sound_name
    # Allow "Tink.aiff" or "Tink"
    stem = Path(str(stem)).stem
    sounds_dir = system_sounds_dir(settings, catalog)
    for ext in (".aiff", ".AIFF", ".wav", ".WAV"):
        candidate = sounds_dir / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    print(f"  warning: system sound not found for '{sound_name}' ({sounds_dir / stem}.aiff)")
    return None


def load_sim_events(slug: str, renders_dir: Path | None = None) -> list[dict]:
    """Load Blender-written impact events for a concept slug."""
    renders_dir = Path(renders_dir) if renders_dir else Path("outputs/renders")
    path = renders_dir / f"{slug}_events.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    events = data.get("events") if isinstance(data, dict) else data
    return list(events or [])


def _segment_anchors(base_segments: list[dict]) -> dict[str, float]:
    """Map role -> absolute start time on the concatenated base track."""
    anchors: dict[str, float] = {}
    cursor = 0.0
    for seg in base_segments:
        role = seg.get("role") or ""
        anchors[role] = cursor
        path = Path(seg["path"])
        cursor += get_duration(path) if path.exists() else float(seg.get("duration") or 0.0)
    return anchors


def resolve_sfx_cues(concept: dict, video_template: dict, base_segments: list[dict],
                     sim_events: list[dict] | None = None,
                     settings: dict | None = None) -> list[dict]:
    """Build timed SFX cues from template fixed anchors + optional sim events.

    Returns list of ``{path, start, volume}``.
    """
    video_template = video_template or {}
    sfx_cfg = video_template.get("sfx") or {}
    if sfx_cfg.get("enabled") is False:
        return []

    catalog = load_catalog()
    settings = settings or {}
    base_vol = float(
        sfx_cfg.get("volume",
                    settings.get("compositing", {}).get("sfx_volume", 0.55))
    )
    anchors = _segment_anchors(base_segments)
    cues: list[dict] = []

    for cue in sfx_cfg.get("cues") or []:
        at = cue.get("at", "")
        role = _ANCHOR_ALIASES.get(at, at)
        if role not in anchors:
            continue
        sound = cue.get("sound") or role
        path = resolve_sfx_path(sound, settings, catalog)
        if not path:
            continue
        vol = float(cue.get("volume", base_vol))
        cues.append({"path": path, "start": round(anchors[role], 3), "volume": vol})

    if sfx_cfg.get("scene_events", True) and sim_events:
        event_sound = sfx_cfg.get("scene_event_sound") or "Tink"
        path = resolve_sfx_path(event_sound, settings, catalog)
        sim_start = anchors.get("sim", 0.0)
        if path:
            n = max(1, len(sim_events))
            for i, ev in enumerate(sim_events):
                t = float(ev.get("t", 0.0))
                # Mild fade across the chain so the end isn't louder than the start.
                fade = 1.0 - 0.35 * (i / max(1, n - 1))
                cues.append({
                    "path": path,
                    "start": round(sim_start + t, 3),
                    "volume": round(base_vol * 0.75 * fade, 3),
                })

    cues.sort(key=lambda c: c["start"])
    return cues
