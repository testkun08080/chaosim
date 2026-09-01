"""Resolve BGM and SFX for compose, and time the cues onto the timeline.

Sound *files* are chosen in :mod:`pipeline.sfx_library` (shipped -> generated ->
macOS system sound). This module decides *when* each one fires and how loud,
which is where ``docs/sfx-design.md`` says the satisfying-ness actually lives:

* an event's ``intensity`` picks the variant and sets the volume, so a glancing
  hit and a wall collapsing are no longer the same sound at the same level;
* events closer together than the ear can separate are thinned, because a
  hundred overlapping one-shots read as mud, not as a hundred impacts;
* each hit is pitched a few percent off so a chain stops sounding like one
  sample fired on a timer.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from pipeline.ffmpeg_utils import get_duration
from pipeline import sfx_library

AUDIO_ROOT = Path("assets/audio")
CATALOG_PATH = AUDIO_ROOT / "catalog.yaml"
DEFAULT_SYSTEM_SOUNDS = Path("/System/Library/Sounds")

# Anchor names used by video templates for fixed cue timing.
_ANCHOR_ALIASES = {
    "intro_start": "intro",
    "sim_start": "sim",
    "outro_start": "outro",
}

# Two impacts closer than this are heard as one, so firing both only muddies
# the attack of the first. Blender bakes can emit dozens inside a single frame.
POLYPHONY_MIN_GAP_SEC = 0.04

# How far each hit is detuned, as a fraction of the sample rate. Small enough to
# read as the same object struck twice, large enough to break the machine-gun.
PITCH_JITTER = 0.06

# intensity 0-1 -> a multiplier on the base SFX volume. The floor keeps a very
# light event audible; the ceiling keeps a heavy one from clipping the mix.
VOLUME_FLOOR = 0.35
VOLUME_CEILING = 1.15


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

    return resolve_generated_bgm(concept, catalog, default_mood)


def resolve_generated_bgm(concept: dict, catalog: dict, default_mood: str) -> Path | None:
    """Fall back to generated music when no BGM file matches the mood.

    Same cache-by-prompt rule as the sound effects, so a mood is paid for once
    across every concept that asks for it.
    """
    prompts = catalog.get("bgm_prompts") or {}
    if not prompts:
        return None

    mood = str(concept.get("music_mood") or "").lower()
    key = next((k for k in prompts if k.lower() in mood), None) or default_mood
    prompt = prompts.get(key) or prompts.get("ambient")
    if not prompt:
        return None

    duration = int(float(concept.get("duration_sec") or 30) + 10)
    return sfx_library.generate_music(prompt, duration, name=key,
                                      generate_missing=should_generate())


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
        cues += resolve_event_cues(
            sim_events, anchors.get("sim", 0.0), base_vol,
            catalog=catalog, settings=settings,
            fallback_sound=sfx_cfg.get("scene_event_sound") or "Tink",
            generate_missing=should_generate(sfx_cfg),
        )

    cues.sort(key=lambda c: c["start"])
    return cues


def should_generate(sfx_cfg: dict | None = None) -> bool:
    """Whether compose may generate a missing sound rather than skip it.

    Generation costs money, and a compose that quietly bills for forty one-shots
    is a bad surprise — so the paid path is opt-in (``CHAOSIM_SFX_GENERATE=1``,
    or ``sfx.generate`` in the video template) and ``sfx-build`` is the explicit
    place to spend. The exception is when there is no sandbox to bill: then
    "generating" writes a free placeholder tone, and filling the cache keeps the
    mix audible in CI and on a machine with no macOS system sounds.
    """
    from pipeline import comfyui

    if os.environ.get("CHAOSIM_SFX_GENERATE", "").lower() in ("1", "true", "yes"):
        return True
    if (sfx_cfg or {}).get("generate"):
        return True
    return not comfyui.comfyui_available()


def thin_events(events: list[dict], min_gap: float = POLYPHONY_MIN_GAP_SEC) -> list[dict]:
    """Drop events too close to the previous one to be heard separately.

    Keeps the loudest of a cluster rather than the first: when a stack settles,
    the hit that carries the moment is not necessarily the earliest one.
    """
    ordered = sorted(events, key=lambda e: float(e.get("t", 0.0)))
    kept: list[dict] = []
    for event in ordered:
        t = float(event.get("t", 0.0))
        if kept and t - float(kept[-1].get("t", 0.0)) < min_gap:
            if float(event.get("intensity", 0.6)) > float(kept[-1].get("intensity", 0.6)):
                kept[-1] = event
            continue
        kept.append(event)
    return kept


def _pitch_for(index: int) -> float:
    """A deterministic detune per hit, cycling through five offsets.

    Deterministic on purpose: the same concept must mix to the same audio twice,
    or a re-render becomes a different video and the SFX report stops comparing
    like with like.
    """
    offsets = (0.0, PITCH_JITTER, -PITCH_JITTER * 0.6,
               PITCH_JITTER * 0.5, -PITCH_JITTER)
    return round(1.0 + offsets[index % len(offsets)], 4)


def resolve_event_cues(sim_events: list[dict], sim_start: float, base_vol: float,
                       catalog: dict | None = None, settings: dict | None = None,
                       fallback_sound: str = "Tink",
                       generate_missing: bool = False) -> list[dict]:
    """Turn typed simulation events into timed, graded, varied cues."""
    catalog = catalog or load_catalog()
    events = thin_events(sim_events)
    fallback = resolve_sfx_path(fallback_sound, settings, catalog)

    occurrences: dict[str, int] = {}
    cues: list[dict] = []
    for index, event in enumerate(events):
        event_type = str(event.get("type") or "impact")
        intensity = event.get("intensity", 0.6)
        occurrence = occurrences.get(event_type, 0)
        occurrences[event_type] = occurrence + 1

        path, origin = sfx_library.resolve_event_sound(
            catalog, event_type, intensity, occurrence=occurrence,
            generate_missing=generate_missing,
        )
        if path is None:
            path, origin = fallback, ("system" if fallback else "none")
        if path is None:
            continue

        try:
            scaled = float(intensity)
        except (TypeError, ValueError):
            scaled = 0.6
        gain = VOLUME_FLOOR + (VOLUME_CEILING - VOLUME_FLOOR) * min(1.0, max(0.0, scaled))
        cues.append({
            "path": path,
            "start": round(sim_start + float(event.get("t", 0.0)), 3),
            "volume": round(base_vol * gain, 3),
            "pitch": _pitch_for(index),
            "type": event_type,
            "intensity": round(scaled, 3),
            "origin": origin,
        })
    return cues
