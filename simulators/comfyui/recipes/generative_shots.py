"""Fully generated footage: a list of shots, each prompt -> keyframe -> video.

The concept declares the cut list. One shot becomes one ComfyUI job and one
clip; the clips are concatenated into the single ``<slug>.mp4`` that every
downstream stage already expects, so nothing after the render stage has to know
this footage was generated rather than simulated.

Two prompts per shot, deliberately kept apart:

* ``keyframe_prompt`` decides the **picture** — framing, material, light.
* ``prompt`` decides the **motion** — what moves, and whether the camera holds.

Mixing them is what makes generated shots drift, because the image model reads
motion words as composition and the video model reads composition words as
camera moves.
"""

from __future__ import annotations

# 9:16 is 0.5625; 768x1344 (0.571) is the closest Recraft V4 offers.
DEFAULT_KEYFRAME_SIZE = "768x1344"
DEFAULT_RESOLUTION = "480P"
# Wan's Image-to-Video takes 5/10/15 seconds only.
ALLOWED_DURATIONS = (5, 10, 15)
DEFAULT_DURATION = 5

DEFAULT_KEYFRAME_NEGATIVE = "text, watermark, people, hands, logo, ui, caption"
DEFAULT_MOTION_NEGATIVE = "camera shake, zoom, text, watermark, people, subtitles"


def quantize_duration(seconds: float) -> int:
    """Round a requested shot length to a duration the model actually accepts."""
    try:
        wanted = float(seconds)
    except (TypeError, ValueError):
        return DEFAULT_DURATION
    return min(ALLOWED_DURATIONS, key=lambda allowed: (abs(allowed - wanted), allowed))


def plan_shots(concept: dict, settings: dict | None = None) -> list[dict]:
    """Normalise ``concept["comfyui"]["shots"]`` into the shot list we render.

    Also the single source of truth for shot names and durations, so the cue
    sheet in ``pipeline.sfx_events`` lands on the same timeline the clips do.

    ``config/settings.yaml`` supplies the cheap defaults and the ceiling on how
    many shots one concept may run; the concept can go under them but the
    ceiling always wins, so a runaway YAML cannot spend without an edit there.
    """
    cfg = concept.get("comfyui") or {}
    limits = (settings or {}).get("comfyui") or {}
    resolution = str(cfg.get("resolution") or limits.get("resolution") or DEFAULT_RESOLUTION)
    default_duration = limits.get("shot_duration_sec") or DEFAULT_DURATION
    default_size = cfg.get("keyframe_size") or limits.get("keyframe_size") or DEFAULT_KEYFRAME_SIZE
    base_seed = int(cfg.get("seed") or 0)
    ceiling = int(limits.get("max_shots") or 0)
    asked = int(cfg.get("max_shots") or 0)
    max_shots = min(x for x in (ceiling, asked) if x > 0) if (ceiling or asked) else 0

    shots: list[dict] = []
    for index, raw in enumerate(cfg.get("shots") or [], start=1):
        duration = quantize_duration(raw.get("duration", default_duration))
        shots.append({
            "name": str(raw.get("name") or f"shot_{index:02d}"),
            "index": index,
            "duration": duration,
            "keyframe_prompt": str(raw.get("keyframe_prompt") or raw.get("prompt") or ""),
            "keyframe_negative": str(raw.get("keyframe_negative") or DEFAULT_KEYFRAME_NEGATIVE),
            "keyframe_size": str(raw.get("keyframe_size") or default_size),
            "prompt": str(raw.get("prompt") or ""),
            "negative_prompt": str(raw.get("negative_prompt") or DEFAULT_MOTION_NEGATIVE),
            "resolution": str(raw.get("resolution") or resolution),
            "seed": int(raw.get("seed") if raw.get("seed") is not None else base_seed + index),
            "generate_audio": bool(raw.get("generate_audio", False)),
            "cues": list(raw.get("cues") or []),
        })
    if max_shots > 0:
        shots = shots[:max_shots]
    return shots


def build_jobs(concept: dict, params: dict | None = None,
               settings: dict | None = None) -> list[dict]:
    """One ComfyUI job per shot.

    ``video_with_audio`` is picked for a shot that asks the model to generate
    its own audio, because that workflow also writes the audio track out on its
    own — which is what makes the generated soundtrack comparable against our
    own generated SFX in ``sfx-report``.
    """
    slug = concept.get("slug", "render")
    jobs: list[dict] = []
    for shot in plan_shots(concept, settings):
        name = shot["name"]
        if shot["generate_audio"]:
            workflow = "08_video/video_with_audio.json"
            inputs = {
                "prompt": shot["prompt"],
                "negative_prompt": shot["negative_prompt"],
                "resolution": shot["resolution"],
                "duration": shot["duration"],
                "seed": shot["seed"],
                "prefix": f"{slug}/{name}",
                "audio_prefix": f"{slug}/{name}_track",
            }
        else:
            workflow = "08_video/keyframe_then_video.json"
            inputs = {
                "keyframe_prompt": shot["keyframe_prompt"],
                "keyframe_negative": shot["keyframe_negative"],
                "keyframe_size": shot["keyframe_size"],
                "keyframe_seed": shot["seed"],
                "keyframe_prefix": f"{slug}/{name}_keyframe",
                "prompt": shot["prompt"],
                "negative_prompt": shot["negative_prompt"],
                "resolution": shot["resolution"],
                "duration": shot["duration"],
                "seed": shot["seed"],
                "generate_audio": False,
                "prefix": f"{slug}/{name}",
            }
        jobs.append({
            "workflow": workflow,
            "inputs": inputs,
            "name": name,
            "duration": shot["duration"],
            "cues": shot["cues"],
        })
    return jobs
