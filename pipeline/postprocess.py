"""FFmpeg post-processing for rendered videos."""

import json
import re
import subprocess
from pathlib import Path

from pipeline.ffmpeg_utils import (
    drawtext_font_prefix,
    escape_drawtext,
    ffmpeg_bin,
    has_audio_stream,
    run_ffmpeg,
)


def add_text_overlay(input_path: Path, output_path: Path, caption: str) -> Path:
    """Burn caption text into the video."""
    text = escape_drawtext(caption)
    run_ffmpeg([
        "-i", str(input_path),
        "-vf", (
            f"drawtext={drawtext_font_prefix()}text='{text}':"
            "fontcolor=white:fontsize=48:x=(w-text_w)/2:y=h-100:"
            "shadowcolor=black:shadowx=2:shadowy=2"
        ),
        "-c:a", "copy",
        str(output_path),
    ])
    return output_path


def add_background_music(video_path: Path, audio_path: Path, output_path: Path,
                         volume: float = 0.3) -> Path:
    """Mix background music under the video.

    If the source video has no audio track, the music becomes the sole audio
    track (the previous unconditional ``amix=inputs=2`` failed in that case).
    """
    if has_audio_stream(video_path):
        filt = f"[1:a]volume={volume}[bg];[0:a][bg]amix=inputs=2[aout]"
        run_ffmpeg([
            "-i", str(video_path),
            "-i", str(audio_path),
            "-filter_complex", filt,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-shortest",
            str(output_path),
        ])
    else:
        run_ffmpeg([
            "-i", str(video_path),
            "-i", str(audio_path),
            "-filter_complex", f"[1:a]volume={volume}[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-shortest",
            str(output_path),
        ])
    return output_path


# YouTube normalises anything louder than this back down, so mastering above it
# only costs dynamic range. TP below 0 leaves headroom for the lossy encode.
LOUDNESS_TARGET = "I=-14:LRA=11:TP=-1.5"


def ensure_shorts_format(input_path: Path, output_path: Path,
                         loudnorm: bool = True) -> Path:
    """Ensure video is 9:16, max 59s, H.264/AAC for Shorts compatibility.

    Also normalises loudness to the streaming target. Without it every video
    lands wherever its own mix happened to fall — one clip inaudible, the next
    one clipping — which is the single cheapest audio fix available
    (``docs/sfx-design.md`` §5).
    """
    args = [
        "-i", str(input_path),
        "-t", "59",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level", "4.0",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
    ]
    # A silent track has nothing to measure, and normalising one anyway just
    # raises the noise floor of an otherwise clean video.
    if loudnorm and has_audio_stream(Path(input_path)):
        args += ["-af", loudnorm_filter(Path(input_path))]
    run_ffmpeg(args + [str(output_path)])
    return output_path


def measure_loudness(path: Path) -> dict | None:
    """Measure a file's loudness with ffmpeg's own analyser. None if it fails.

    Used both to build the second pass of ``loudnorm`` and to report what a
    finished video actually came out at.
    """
    proc = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path),
         "-af", f"loudnorm={LOUDNESS_TARGET}:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    # The JSON block is the last thing loudnorm writes to stderr.
    match = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match[-1])
    except json.JSONDecodeError:
        return None


def loudnorm_filter(path: Path) -> str:
    """The ``loudnorm`` filter string, measured where possible.

    Single-pass loudnorm has to guess as it goes and lands a few LU off target.
    Measuring first and handing the numbers back lets ffmpeg apply one linear
    gain change instead, which hits the target and leaves the transients alone —
    the part that matters for a video whose appeal is its impacts.

    ffmpeg still drops back to dynamic mode when the source's loudness range is
    wider than the target LRA (a near-silent clip punctuated by hits does this),
    so this is an improvement, not a guarantee. ``sfx-report`` measures what the
    finished file actually came out at rather than assuming.

    Falls back to single-pass if the measurement does not come back.
    """
    measured = measure_loudness(path)
    if not measured:
        return f"loudnorm={LOUDNESS_TARGET}"
    try:
        return (
            f"loudnorm={LOUDNESS_TARGET}"
            f":measured_I={float(measured['input_i'])}"
            f":measured_LRA={float(measured['input_lra'])}"
            f":measured_TP={float(measured['input_tp'])}"
            f":measured_thresh={float(measured['input_thresh'])}"
            f":linear=true:print_format=summary"
        )
    except (KeyError, TypeError, ValueError):
        return f"loudnorm={LOUDNESS_TARGET}"
