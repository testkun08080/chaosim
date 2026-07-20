"""HTML -> video material via the HyperFrames CLI (with an ffmpeg stub fallback).

HyperFrames (https://github.com/heygen-com/hyperframes) is a Node.js CLI that
renders an HTML ``index.html`` composition to MP4 using headless Chromium +
ffmpeg. We drive it as a subprocess, exactly like Blender in ``renderer.py``.

When HyperFrames is not installed (or ``CHAOSIM_STUB=1``), every render falls
back to an ffmpeg-generated placeholder so the rest of the pipeline still runs.
"""

import os
import shlex
import shutil
import subprocess
from pathlib import Path

from pipeline.config import stub_mode
from pipeline.ffmpeg_utils import drawtext_font_prefix, escape_drawtext, run_ffmpeg
from pipeline.templating import render_to_file, build_context


def get_hyperframes_cmd() -> list[str]:
    """Base command for invoking HyperFrames (override with HYPERFRAMES_PATH)."""
    custom = os.environ.get("HYPERFRAMES_PATH")
    if custom:
        parts = shlex.split(custom)
        # Resolve relative binaries like ./node_modules/.bin/hyperframes
        if parts and not parts[0].startswith("-"):
            candidate = Path(parts[0])
            if not candidate.is_absolute():
                candidate = (Path.cwd() / candidate).resolve()
            if candidate.exists():
                parts[0] = str(candidate)
        return parts
    local = Path("node_modules/.bin/hyperframes")
    if local.exists():
        return [str(local.resolve())]
    which = shutil.which("hyperframes")
    if which:
        return [which]
    return ["npx", "--yes", "hyperframes"]


def hyperframes_available() -> bool:
    """True if the HyperFrames CLI can be invoked (and stub mode is off)."""
    if stub_mode():
        return False
    cmd = get_hyperframes_cmd()
    if cmd[0] == "npx":
        if shutil.which("npx") is None:
            return False
        probe = cmd + ["--version"]
    else:
        if shutil.which(cmd[0]) is None and not os.path.isfile(cmd[0]):
            return False
        probe = cmd + ["--version"]
    try:
        env = os.environ.copy()
        # Avoid npm's noisy unknown-config warnings breaking parsers.
        result = subprocess.run(probe, capture_output=True, timeout=120, env=env)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _set_gsap_src(ctx: dict) -> None:
    """Set ctx['gsap_src'] to a local or remote GSAP URL.

    If GSAP is available locally (vendored in work_dir or from a package),
    use a local path. Otherwise use the CDN. This avoids TLS failures in
    sandboxes where jsdelivr is unreachable.
    """
    # Try .agents/skills/graphic-overlays/assets/vendor/gsap.min.js (from hyperframes skills)
    local_gsap = Path(".agents/skills/graphic-overlays/assets/vendor/gsap.min.js")
    if local_gsap.exists():
        ctx["gsap_src"] = f"file://{local_gsap.resolve()}"
    # Otherwise fall back to CDN (will fail gracefully in sandboxes with offline CDN)
    # and the base template will output data-composition-id + data-duration for HyperFrames to infer timing


def prepare_composition(html: str, work_dir: Path, assets: list[Path] | None = None) -> Path:
    """Write ``index.html`` (and copy any assets) into a composition directory."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "index.html").write_text(html, encoding="utf-8")
    for asset in assets or []:
        shutil.copy(asset, work_dir / Path(asset).name)
    return work_dir


def render_composition(work_dir: Path, output_path: Path, width: int = 1080,
                       height: int = 1920, fps: int = 60,
                       transparent: bool = False) -> Path:
    """Render a composition directory to a video via the HyperFrames CLI.

    Output dimensions come from the composition's own ``data-width``/
    ``data-height``; for the common 1080x1920 case we also pass the
    ``portrait`` resolution preset. Transparency is requested via ``--format webm``.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = get_hyperframes_cmd() + [
        "render", str(work_dir),
        "-o", str(output_path),
        "-f", str(fps),
    ]
    if transparent:
        cmd += ["--format", "webm"]
    if (width, height) == (1080, 1920):
        cmd += ["--resolution", "portrait"]
    elif (width, height) == (1920, 1080):
        cmd += ["--resolution", "landscape"]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"HyperFrames render failed ({result.returncode}) for {work_dir}")
    return output_path


def render_still(work_dir: Path, output_png: Path, at_sec: float = 0.0) -> Path:
    """Capture a single frame via ``hyperframes snapshot`` and move it to output."""
    output_png = Path(output_png)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    cmd = get_hyperframes_cmd() + [
        "snapshot", str(work_dir),
        "--frames", "1", "--at", str(at_sec),
    ]
    result = subprocess.run(cmd, cwd=str(work_dir))
    if result.returncode != 0:
        raise RuntimeError(f"HyperFrames snapshot failed ({result.returncode})")
    # snapshot writes PNG(s) under the project dir; pick the newest and move it.
    pngs = sorted(Path(work_dir).rglob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not pngs:
        raise RuntimeError("HyperFrames snapshot produced no PNG")
    shutil.copy(pngs[0], output_png)
    return output_png


def render_segment_from_template(template_name: str, concept: dict, settings: dict,
                                 output_path: Path, video_template: dict | None = None,
                                 segment_cfg: dict | None = None,
                                 transparent: bool = False) -> Path:
    """High-level: render an HTML template to a video segment (or stub)."""
    ctx = build_context(concept, settings, segment_cfg, video_template)
    ctx["transparent"] = transparent
    duration = float((segment_cfg or {}).get("duration", 3.0) or 3.0)
    _set_gsap_src(ctx)

    if not hyperframes_available():
        print(f"  HyperFrames unavailable — stubbing segment '{template_name}'")
        return _stub_segment(ctx, Path(output_path), duration, transparent)

    print(f"  HyperFrames rendering '{template_name}' -> {output_path}")
    output_path = Path(output_path)
    work_dir = output_path.parent / f"_work_{output_path.stem}"
    html = render_to_file("hyperframes", template_name, ctx, work_dir / "index.html").read_text()
    prepare_composition(html, work_dir)
    return render_composition(work_dir, output_path, width=ctx["width"],
                              height=ctx["height"], fps=ctx["fps"], transparent=transparent)


def render_still_from_template(template_name: str, concept: dict, settings: dict,
                               output_png: Path, video_template: dict | None = None,
                               segment_cfg: dict | None = None,
                               size: tuple[int, int] = (1280, 720)) -> Path:
    """Render an HTML thumbnail template to a single PNG (or stub)."""
    ctx = build_context(concept, settings, segment_cfg, video_template)
    ctx["width"], ctx["height"] = size
    _set_gsap_src(ctx)

    if not hyperframes_available():
        return _stub_still(ctx, Path(output_png), size)

    output_png = Path(output_png)
    work_dir = output_png.parent / f"_work_{output_png.stem}"
    html = render_to_file("thumbnail", template_name, ctx, work_dir / "index.html").read_text()
    prepare_composition(html, work_dir)
    return render_still(work_dir, output_png)


# --- ffmpeg stub fallbacks -------------------------------------------------

def _drawtext(text: str, fontsize: int, y: str, color: str = "white") -> str:
    return (f"drawtext={drawtext_font_prefix()}text='{escape_drawtext(text)}':"
            f"fontcolor={color}:fontsize={fontsize}:x=(w-text_w)/2:y={y}:"
            "shadowcolor=black:shadowx=3:shadowy=3:line_spacing=12")


def _stub_segment(ctx: dict, output_path: Path, duration: float, transparent: bool) -> Path:
    """Generate an equivalent segment with ffmpeg when HyperFrames is unavailable."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    w, h, fps = ctx["width"], ctx["height"], ctx["fps"]
    title = ctx.get("title") or ctx.get("text") or ""
    sub = ctx.get("text") if ctx.get("text") and title != ctx.get("text") else ctx.get("hook", "")

    filters = []
    if title:
        filters.append(_drawtext(title, 90, "(h-text_h)/2-80"))
    if sub:
        filters.append(_drawtext(sub, 52, "(h-text_h)/2+120", color=ctx.get("accent", "#4fd1c5")))

    if transparent:
        # Transparent VP9/alpha overlay material.
        src = f"color=c=black@0.0:s={w}x{h}:d={duration}:r={fps}"
        vf = ",".join(filters) if filters else "null"
        run_ffmpeg([
            "-f", "lavfi", "-i", src,
            "-vf", f"format=yuva420p,{vf}",
            "-c:v", "vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
            str(output_path),
        ])
    else:
        bg = ctx.get("bg_color", "#0a0a12").lstrip("#")
        src = f"color=c=0x{bg}:s={w}x{h}:d={duration}:r={fps}"
        vf = ",".join(filters) if filters else "null"
        run_ffmpeg([
            "-f", "lavfi", "-i", src,
            "-vf", vf,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(duration),
            str(output_path),
        ])
    return output_path


def _stub_still(ctx: dict, output_png: Path, size: tuple[int, int]) -> Path:
    output_png.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    bg = ctx.get("bg_color", "#0a0a12").lstrip("#")
    headline = ctx.get("headline") or ctx.get("title") or ""
    filters = [_drawtext(headline, max(48, w // 14), "(h-text_h)/2")]
    run_ffmpeg([
        "-f", "lavfi", "-i", f"color=c=0x{bg}:s={w}x{h}",
        "-vf", ",".join(filters),
        "-frames:v", "1",
        str(output_png),
    ])
    return output_png
