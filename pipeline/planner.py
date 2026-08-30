"""AI-driven concept generation using Claude API."""

import json
import anthropic
from pathlib import Path
import yaml

CONCEPT_SCHEMA = {
    "title": "str",
    "slug": "str (snake_case, used as filename)",
    "source": "blender | comfyui | hybrid (which backend makes the footage)",
    "simulator": "blender | houdini | unreal",
    "scene_script": "str (filename in simulators/blender/scenes/; blender and hybrid only)",
    "duration_sec": "int",
    "description": "str (1-2 sentences)",
    "hook": "str (first 3 seconds action that grabs attention)",
    "viral_angle": "str (why this will get shares/views)",
    "params": "dict (scene-specific parameters)",
    "render_preset": "preview | medium | high | ultra",
    "music_mood": "str",
    "caption": "str (YouTube title, max 100 chars)",
    "hashtags": ["list of strings"],
    "video_template": "str (name under templates/video/, e.g. default_shorts or minimal)",
    "narration": {
        "lines": ["list of short Japanese narration sentences, one per beat (3-6 lines)"],
        "speaker": "int (VOICEVOX speaker id, default 3)",
        "speed": "float (default 1.0)",
    },
    "thumbnail": {
        "style": "str (template name: bold_headline or vertical_cover)",
        "headline": "str (<= ~16 Japanese chars, punchy)",
    },
    "bgm": "str (optional path to a background-music file, or omit)",
}

# Extra fields a `source: comfyui` concept needs. Kept apart from CONCEPT_SCHEMA
# so the Blender prompt is not padded with fields it must never fill in.
COMFYUI_SCHEMA = {
    "source": "comfyui",
    "comfyui": {
        "recipe": "generative_shots",
        "resolution": "480P (keep it here; 720P/1080P cost 2-3x more)",
        "seed": "int",
        "shots": [
            {
                "name": "shot_01",
                "keyframe_prompt": "str — the PICTURE only: framing, material, light. No motion words.",
                "prompt": "str — the MOTION only: what moves, and whether the camera holds still.",
                "duration": "int (5, 10 or 15 — the model accepts nothing else)",
                "cues": [
                    {
                        "t": "float — seconds from the START OF THIS SHOT",
                        "type": "impact | drop | collapse | whoosh | settle | tick",
                        "intensity": "float 0-1 (drives volume and which sound is picked)",
                    }
                ],
            }
        ],
    },
}

COMFYUI_PROMPT = """This concept is rendered by generating video from prompts (ComfyUI), not by
simulating physics. That changes what a good concept looks like:

- Pick a subject whose appeal survives approximate physics: sand, powder, fluid,
  shattering glass, crushing, melting. Avoid anything the viewer can count or
  verify (a domino chain that must not skip, a face-count comparison).
- Break the video into 2-5 shots of 5 seconds each. Each shot is generated
  independently, so a shot must read on its own; do not write "continues from
  the previous shot".
- Keep `keyframe_prompt` and `prompt` strictly separate. The image model reads
  motion words as composition, and the video model reads composition words as
  camera moves; mixing them is what makes shots drift.
- Say "the camera holds still" in `prompt` unless a move is the point. Generated
  camera drift ruins the satisfying, locked-off look this format depends on.
- Write `cues` for every moment a sound should land, timed from the start of
  that shot. This is the only timing information the sound stage will have, so
  a shot with visible impacts and no cues will be silent."""

SYSTEM_PROMPT = """You are a viral short-form video producer specializing in physics simulations and chaos theory visualizations.
Your goal: create concepts for 9:16 vertical videos (max 59s) that are visually stunning, scientifically interesting, and optimized for YouTube Shorts/TikTok virality.

Rules:
- The hook must happen in the FIRST 3 SECONDS (crucial for retention)
- Visual appeal > scientific accuracy (though both are great)
- Satisfying, hypnotic, or surprising outcomes perform best
- Narration lines must be in natural Japanese, short and punchy (one idea per line)
- Output valid JSON matching the schema exactly
"""

# Defaults filled in when a concept omits the newer fields (backward compatible).
DEFAULT_VIDEO_TEMPLATE = "default_shorts"


def build_local_concept(topic: str) -> dict:
    """Build a ready-to-render concept without calling Claude.

    Uses the lightweight domino scene so the full pipeline can be exercised
    even when ANTHROPIC_API_KEY is unset.
    """
    import re
    import unicodedata

    slug_base = unicodedata.normalize("NFKD", topic).encode("ascii", "ignore").decode()
    slug_base = re.sub(r"[^a-zA-Z0-9]+", "_", slug_base).strip("_").lower()
    if not slug_base:
        slug_base = "domino"
    if slug_base.startswith("local_"):
        slug = slug_base[:48]
    else:
        slug = f"local_{slug_base}"[:48]
    return {
        "title": f"{topic} — ドミノ連鎖",
        "slug": slug,
        "simulator": "blender",
        "scene_script": "domino_chain",
        "duration_sec": 6,
        "description": f"{topic}を題材にした、短いカラフルドミノの連鎖シミュレーション。",
        "hook": "最初のドミノが倒れた瞬間から連鎖が始まる",
        "viral_angle": "短いドミノ連鎖は満足感が高く、ショート動画のフックとして使いやすい。",
        "params": {
            "domino_count": 12,
            "spacing": 0.32,
            "domino_height": 0.8,
            "domino_width": 0.4,
            "domino_depth": 0.1,
            "curve_radius": 0,
        },
        "render_preset": "preview",
        "music_mood": "upbeat",
        "caption": f"{topic}のドミノ連鎖 #shorts #dominos #satisfying",
        "hashtags": ["dominos", "chainreaction", "satisfying", "physics", "shorts"],
        "video_template": DEFAULT_VIDEO_TEMPLATE,
        "narration": {
            "enabled": True,
            "speaker": 3,
            "speed": 1.05,
            "lines": [
                "最初のドミノを倒すと…",
                "バタバタと連鎖が広がる！",
                "物理の力って気持ちいい。",
            ],
        },
        "thumbnail": {
            "style": "vertical_cover",
            "headline": "ドミノ連鎖",
        },
    }


def generate_concept(topic: str, client: anthropic.Anthropic,
                    source: str = "blender") -> dict:
    """Generate a video concept for the given topic using Claude.

    ``source`` picks which backend the concept is written for; a ComfyUI
    concept needs a cut list and a cue sheet instead of scene params.
    """
    if source == "comfyui":
        schema = {**CONCEPT_SCHEMA, **COMFYUI_SCHEMA}
        schema.pop("scene_script", None)
        schema.pop("params", None)
        guidance = COMFYUI_PROMPT
    else:
        schema = CONCEPT_SCHEMA
        guidance = (
            "The concept must be implementable as a Blender Python script.\n"
            "For `params`, include all numeric parameters needed by the scene script "
            "(e.g., gravity, viscosity, particle_count, etc.)\n"
            "For `scene_script`, use one of: double_pendulum, fluid_ink, sand_collapse, "
            "lorenz_attractor, domino_chain, or suggest a new filename."
        )

    prompt = f"""Generate a viral chaos simulation video concept for: "{topic}"

Output a single JSON object with these fields:
{json.dumps(schema, indent=2, ensure_ascii=False)}

{guidance}
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text
    # Extract JSON from response
    start = text.find("{")
    end = text.rfind("}") + 1
    concept = json.loads(text[start:end])
    concept.setdefault("source", source)
    return concept


def save_concept(concept: dict, output_dir: Path) -> Path:
    """Save concept as YAML file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = concept.get("slug", "unnamed")
    path = output_dir / f"{slug}.yaml"
    with open(path, "w") as f:
        yaml.dump(concept, f, allow_unicode=True, sort_keys=False)
    return path


def load_concept(path: Path) -> dict:
    """Load concept from YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def normalize_concept(concept: dict) -> dict:
    """Fill in the newer pipeline fields from the chosen video template.

    Keeps older concept files (which only have the original fields) working by
    deriving narration / segments / thumbnail defaults. Does not mutate input.
    """
    from pipeline.templating import load_video_template

    concept = dict(concept)
    concept.setdefault("source", "blender")
    template_name = concept.get("video_template") or DEFAULT_VIDEO_TEMPLATE
    concept["video_template"] = template_name

    try:
        video_template = load_video_template(template_name)
    except FileNotFoundError:
        video_template = {}

    tmpl_narr = video_template.get("narration", {})
    narration = dict(concept.get("narration") or {})
    narration.setdefault("lines", [])
    narration.setdefault("speaker", tmpl_narr.get("speaker", 3))
    narration.setdefault("speed", tmpl_narr.get("speed", 1.0))
    narration.setdefault("pitch", tmpl_narr.get("pitch", 0.0))
    if "enabled" in tmpl_narr:
        narration.setdefault("enabled", tmpl_narr["enabled"])
    narration.setdefault("source", tmpl_narr.get("source", "default"))
    concept["narration"] = narration

    # Thumbnail orientation follows the selected video format. This also
    # repairs older Shorts concepts that inherited a landscape thumbnail.
    from pipeline.thumbnail import resolve_thumbnail_config
    concept["thumbnail"] = resolve_thumbnail_config(concept, video_template)

    # Segment graph: concept overrides template, otherwise inherit the template's.
    if not concept.get("segments"):
        concept["segments"] = video_template.get("segments", [])

    return concept
