"""AI-driven concept generation using Claude API."""

import json
import anthropic
from pathlib import Path
import yaml

CONCEPT_SCHEMA = {
    "title": "str",
    "slug": "str (snake_case, used as filename)",
    "simulator": "blender | houdini | unreal",
    "scene_script": "str (filename in simulators/blender/scenes/)",
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

def generate_concept(topic: str, client: anthropic.Anthropic) -> dict:
    """Generate a video concept for the given topic using Claude."""
    prompt = f"""Generate a viral chaos simulation video concept for: "{topic}"

The concept must be implementable as a Blender Python script.
Output a single JSON object with these fields:
{json.dumps(CONCEPT_SCHEMA, indent=2)}

For `params`, include all numeric parameters needed by the scene script (e.g., gravity, viscosity, particle_count, etc.)
For `scene_script`, use one of: double_pendulum, fluid_ink, sand_collapse, lorenz_attractor, domino_chain, or suggest a new filename.
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text
    # Extract JSON from response
    start = text.find("{")
    end = text.rfind("}") + 1
    return json.loads(text[start:end])


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

    tmpl_thumb = video_template.get("thumbnail", {})
    thumbnail = dict(concept.get("thumbnail") or {})
    thumbnail.setdefault("style", tmpl_thumb.get("style", "bold_headline"))
    thumbnail.setdefault("size", tmpl_thumb.get("size", [1280, 720]))
    thumbnail.setdefault("headline", concept.get("title", ""))
    concept["thumbnail"] = thumbnail

    # Segment graph: concept overrides template, otherwise inherit the template's.
    if not concept.get("segments"):
        concept["segments"] = video_template.get("segments", [])

    return concept
