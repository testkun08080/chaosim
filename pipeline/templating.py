"""Jinja2 rendering for HyperFrames HTML, narration scripts and video templates.

Templates live under ``templates/`` so users can customise the look of videos
without touching Python. Subdirectories:

- ``templates/hyperframes/`` — HTML compositions (``*.html.j2``)
- ``templates/thumbnail/``   — thumbnail stills (``*.html.j2``)
- ``templates/narration/``   — narration script builders (``*.txt.j2``)
- ``templates/video/``       — top-level video templates (``*.yaml``)
- ``templates/docs/``        — generated documentation views (``*.md.j2``)
"""

from pathlib import Path
import yaml

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Cache one environment per subdir.
_envs: dict[str, Environment] = {}


def get_env(subdir: str) -> Environment:
    if subdir not in _envs:
        autoescape = select_autoescape(["html", "html.j2"]) if subdir in ("hyperframes", "thumbnail") else False
        _envs[subdir] = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR / subdir)),
            autoescape=autoescape,
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _envs[subdir]


def _resolve_name(subdir: str, name: str) -> str:
    """Allow callers to pass a bare name (``intro_title``) or full filename."""
    if name.endswith((".j2", ".html", ".txt", ".yaml")):
        return name
    default_ext = {
        "hyperframes": ".html.j2",
        "thumbnail": ".html.j2",
        "narration": ".txt.j2",
        "docs": ".md.j2",
    }.get(subdir, ".j2")
    return f"{name}{default_ext}"


def render_template(subdir: str, name: str, context: dict) -> str:
    template = get_env(subdir).get_template(_resolve_name(subdir, name))
    return template.render(**context)


def render_to_file(subdir: str, name: str, context: dict, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_template(subdir, name, context), encoding="utf-8")
    return out_path


def load_video_template(name_or_path: str) -> dict:
    """Load a top-level video template from ``templates/video/<name>.yaml``."""
    candidate = Path(name_or_path)
    if candidate.exists():
        path = candidate
    else:
        stem = name_or_path
        if stem.endswith(".yaml"):
            stem = stem[: -len(".yaml")]
        path = TEMPLATES_DIR / "video" / f"{stem}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Video template not found: {name_or_path} ({path})")
    with open(path) as f:
        return yaml.safe_load(f)


def build_context(concept: dict, settings: dict, segment_cfg: dict | None = None,
                  video_template: dict | None = None) -> dict:
    """Merge concept + global + brand + segment settings into one render context."""
    video_template = video_template or {}
    resolution = (video_template.get("resolution")
                  or settings.get("video", {}).get("resolution", [1080, 1920]))
    width, height = resolution[0], resolution[1]
    brand = dict(video_template.get("brand", {}))

    ctx = {
        "title": concept.get("title", ""),
        "hook": concept.get("hook", ""),
        "caption": concept.get("caption", ""),
        "description": concept.get("description", ""),
        "hashtags": concept.get("hashtags", []),
        "width": width,
        "height": height,
        "fps": video_template.get("fps", settings.get("video", {}).get("fps", 60)),
        "bg_color": brand.get("bg_color", "#0a0a12"),
        "accent": brand.get("accent", "#4fd1c5"),
        "text_color": brand.get("text_color", "#ffffff"),
    }
    ctx.update(brand)
    if segment_cfg:
        ctx.update(segment_cfg)
        # Per-segment text override falls through to a sensible default.
        ctx.setdefault("text", segment_cfg.get("text", ""))
    return ctx
