"""YouTube thumbnail generation (HTML template still, with a frame fallback)."""

from pathlib import Path

from pipeline import hyperframes
from pipeline.ffmpeg_utils import drawtext_font_prefix, escape_drawtext, run_ffmpeg


_PORTRAIT_PROFILE = {"style": "vertical_cover", "size": [1080, 1920]}
_LANDSCAPE_PROFILE = {"style": "bold_headline", "size": [1280, 720]}
_BUILTIN_STYLES = {"vertical_cover", "bold_headline"}


def resolve_thumbnail_config(concept: dict, video_template: dict | None = None,
                             settings: dict | None = None) -> dict:
    """Return a thumbnail config whose layout matches the video orientation.

    Portrait videos use a portrait cover; landscape videos (including 16:9)
    use the standard YouTube 1280x720 treatment. Explicit custom styles and
    same-orientation sizes are preserved.
    """
    video_template = video_template or {}
    settings = settings or {}
    resolution = (video_template.get("resolution")
                  or settings.get("video", {}).get("resolution", [1080, 1920]))
    video_w, video_h = int(resolution[0]), int(resolution[1])
    portrait = video_h > video_w
    profile = _PORTRAIT_PROFILE if portrait else _LANDSCAPE_PROFILE

    config = dict(video_template.get("thumbnail") or {})
    config.update(concept.get("thumbnail") or {})

    size = config.get("size")
    valid_size = (
        isinstance(size, (list, tuple))
        and len(size) == 2
        and all(isinstance(value, (int, float)) and value > 0 for value in size)
    )
    size_matches_video = valid_size and ((size[1] > size[0]) == portrait)
    if not size_matches_video:
        config["size"] = list(profile["size"])
    else:
        config["size"] = [int(size[0]), int(size[1])]

    style = config.get("style")
    if not style or (style in _BUILTIN_STYLES and style != profile["style"]):
        config["style"] = profile["style"]
    config.setdefault("headline", concept.get("title", ""))
    return config


def generate_thumbnail(concept: dict, settings: dict, out_png: Path,
                       video_template: dict | None = None,
                       source_video: Path | None = None,
                       size: tuple[int, int] | None = None) -> Path:
    """Render a thumbnail PNG.

    Preferred: HTML template via HyperFrames (falls back to an ffmpeg stub when
    HyperFrames is unavailable). If that fails entirely, extract a frame from
    ``source_video`` and overlay the headline.
    """
    out_png = Path(out_png)
    thumb_cfg = resolve_thumbnail_config(concept, video_template, settings)
    style = thumb_cfg["style"]
    size = tuple(size or thumb_cfg["size"])
    headline = thumb_cfg.get("headline") or concept.get("title", "")
    seg_cfg = {"headline": headline, "kicker": concept.get("hook", "")}

    try:
        return hyperframes.render_still_from_template(
            style, concept, settings, out_png,
            video_template=video_template, segment_cfg=seg_cfg, size=size,
        )
    except Exception:  # noqa: BLE001 — any failure falls back to a frame grab.
        if source_video and Path(source_video).exists():
            return _frame_thumbnail(out_png, Path(source_video), headline, size)
        raise


def _frame_thumbnail(out_png: Path, source_video: Path, headline: str,
                     size: tuple[int, int]) -> Path:
    """Extract a frame from the source video and overlay the headline."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
        f"drawtext={drawtext_font_prefix()}text='{escape_drawtext(headline)}':"
        f"fontcolor=white:fontsize={max(48, w // 14)}:x=(w-text_w)/2:y=h-text_h-80:"
        f"box=1:boxcolor=black@0.5:boxborderw=28:shadowcolor=black:shadowx=3:shadowy=3"
    )
    run_ffmpeg([
        "-ss", "1", "-i", str(source_video),
        "-vf", vf, "-frames:v", "1", str(out_png),
    ])
    return out_png
