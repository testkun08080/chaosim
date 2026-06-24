"""Assemble the final 9:16 video from segments + narration + BGM + captions."""

from pathlib import Path

from pipeline.ffmpeg_utils import (
    drawtext_font_prefix,
    escape_drawtext,
    get_duration,
    run_ffmpeg,
)
from pipeline.postprocess import ensure_shorts_format


def concat_segments(paths: list[Path], out_path: Path, fps: int = 60,
                    w: int = 1080, h: int = 1920) -> Path:
    """Concatenate video segments (video only), normalising size/fps/SAR."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    inputs: list[str] = []
    filters: list[str] = []
    for i, p in enumerate(paths):
        inputs += ["-i", str(p)]
        filters.append(
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p[v{i}]"
        )
    concat_in = "".join(f"[v{i}]" for i in range(len(paths)))
    filters.append(f"{concat_in}concat=n={len(paths)}:v=1:a=0[outv]")
    run_ffmpeg(inputs + [
        "-filter_complex", ";".join(filters),
        "-map", "[outv]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out_path),
    ])
    return out_path


def overlay_segment(base: Path, overlay: Path, out_path: Path, start: float,
                    x: str = "0", y: str = "0") -> Path:
    """Overlay a (transparent) material clip onto the base starting at ``start``."""
    out_path = Path(out_path)
    run_ffmpeg([
        "-i", str(base),
        "-itsoffset", f"{start}", "-i", str(overlay),
        "-filter_complex", f"[0:v][1:v]overlay=x={x}:y={y}:eof_action=pass[v]",
        "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out_path),
    ])
    return out_path


def burn_caption_segments(video: Path, caption_segments: list[dict], out_path: Path,
                          style: dict | None = None) -> Path:
    """Burn time-coded captions (one drawtext per segment) into the video."""
    out_path = Path(out_path)
    if not caption_segments:
        # Nothing to burn — re-encode so downstream sees a consistent file.
        run_ffmpeg(["-i", str(video), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path)])
        return out_path

    style = style or {}
    fontsize = style.get("fontsize", 52)
    y = style.get("y", "h-360")
    font = drawtext_font_prefix()
    parts = []
    for seg in caption_segments:
        txt = escape_drawtext(seg["text"])
        parts.append(
            f"drawtext={font}text='{txt}':fontcolor=white:fontsize={fontsize}:"
            f"x=(w-text_w)/2:y={y}:box=1:boxcolor=black@0.5:boxborderw=24:"
            f"shadowcolor=black:shadowx=2:shadowy=2:"
            f"enable='between(t,{seg['start']},{seg['end']})'"
        )
    run_ffmpeg([
        "-i", str(video), "-vf", ",".join(parts),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path),
    ])
    return out_path


def mix_tracks(video: Path, narration: Path | None, bgm: Path | None, out_path: Path,
               total: float, narration_start: float = 0.0,
               bgm_volume: float = 0.18, narration_volume: float = 1.0) -> Path:
    """Mix narration (delayed) + BGM under the video; always yields an audio track."""
    out_path = Path(out_path)
    inputs: list[str] = ["-i", str(video)]
    filters: list[str] = []
    labels: list[str] = []
    idx = 1
    have_real = False

    if narration and Path(narration).exists() and get_duration(Path(narration)) > 0.05:
        inputs += ["-i", str(narration)]
        d = int(max(0.0, narration_start) * 1000)
        filters.append(f"[{idx}:a]adelay={d}|{d},volume={narration_volume}[a{idx}]")
        labels.append(f"[a{idx}]")
        idx += 1
        have_real = True

    if bgm and Path(bgm).exists():
        inputs += ["-stream_loop", "-1", "-i", str(bgm)]
        filters.append(
            f"[{idx}:a]volume={bgm_volume},atrim=0:{total},asetpts=PTS-STARTPTS[a{idx}]"
        )
        labels.append(f"[a{idx}]")
        idx += 1
        have_real = True

    if not have_real:
        inputs += ["-f", "lavfi", "-t", f"{total}", "-i", "anullsrc=r=24000:cl=mono"]
        labels.append(f"{idx}:a")  # direct input ref (no brackets) for -map
        idx += 1

    if len(labels) == 1:
        amap = labels[0]
    else:
        filters.append("".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0[aout]")
        amap = "[aout]"

    cmd = list(inputs)
    if filters:
        cmd += ["-filter_complex", ";".join(filters)]
    cmd += [
        "-map", "0:v", "-map", amap,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-t", f"{total}",
        str(out_path),
    ]
    run_ffmpeg(cmd)
    return out_path


def compose(concept: dict, video_template: dict, base_segments: list[dict],
            overlay_segments: list[dict], narration_path: Path | None,
            narration_segments: list[dict], bgm_path: Path | None,
            settings: dict, out_path: Path, work_dir: Path) -> Path:
    """Full assembly: concat base -> overlays -> captions -> audio -> shorts format."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    resolution = video_template.get("resolution") or settings.get("video", {}).get("resolution", [1080, 1920])
    w, h = resolution[0], resolution[1]
    fps = video_template.get("fps", settings.get("video", {}).get("fps", 60))
    comp = settings.get("compositing", {})

    # 1. Base track: concat intro/sim/outro in declared order.
    base_paths = [Path(s["path"]) for s in base_segments]
    durations = [get_duration(p) for p in base_paths]
    starts, acc = [], 0.0
    for d in durations:
        starts.append(acc)
        acc += d
    sim_start = next((starts[i] for i, s in enumerate(base_segments) if s.get("role") == "sim"), 0.0)

    base_visual = concat_segments(base_paths, work_dir / "base.mp4", fps=fps, w=w, h=h)

    # 2. Explicitly-timed overlay material (HyperFrames transparent clips).
    visual = base_visual
    for i, ov in enumerate(overlay_segments):
        nxt = work_dir / f"overlay_{i}.mp4"
        overlay_segment(visual, Path(ov["path"]), nxt, ov.get("start", 0.0))
        visual = nxt

    # 3. Captions from narration, time-shifted to when narration starts (sim).
    caption_segments = [
        {"text": s["text"], "start": round(s["start"] + sim_start, 3),
         "end": round(s["end"] + sim_start, 3)}
        for s in (narration_segments or [])
    ]
    captioned = burn_caption_segments(visual, caption_segments, work_dir / "captioned.mp4",
                                      style=comp.get("caption_style"))

    # 4. Mix audio (narration + BGM) under the captioned video.
    total = get_duration(captioned)
    composed = mix_tracks(
        captioned, narration_path, bgm_path, work_dir / "composed.mp4",
        total=total, narration_start=sim_start,
        bgm_volume=comp.get("bgm_volume", 0.18),
        narration_volume=comp.get("narration_volume", 1.0),
    )

    # 5. Final Shorts-compatible encode.
    return ensure_shorts_format(composed, Path(out_path))
