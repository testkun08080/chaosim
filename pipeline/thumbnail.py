"""YouTube thumbnail generation (HTML template still, with a frame fallback)."""

from pathlib import Path

from pipeline import hyperframes
from pipeline.ffmpeg_utils import drawtext_font_prefix, escape_drawtext, run_ffmpeg
from pipeline.templating import build_context


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
    thumb_cfg = concept.get("thumbnail", {}) or {}
    style = thumb_cfg.get("style", "bold_headline")
    size = tuple(size or thumb_cfg.get("size") or (1280, 720))
    headline = thumb_cfg.get("headline") or concept.get("title", "")
    seg_cfg = {"headline": headline, "kicker": concept.get("hook", "")}

    try:
        return hyperframes.render_still_from_template(
            style, concept, settings, out_png,
            video_template=video_template, segment_cfg=seg_cfg, size=size,
        )
    except Exception:  # noqa: BLE001 — any failure falls back to a frame grab.
        if source_video and Path(source_video).exists():
            return _frame_thumbnail(concept, settings, out_png, Path(source_video),
                                    headline, size, video_template)
        raise


def _frame_thumbnail(concept: dict, settings: dict, out_png: Path, source_video: Path,
                     headline: str, size: tuple[int, int],
                     video_template: dict | None) -> Path:
    """Extract a frame from the source video and overlay the headline."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    ctx = build_context(concept, settings, video_template=video_template)
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
