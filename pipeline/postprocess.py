"""FFmpeg post-processing for rendered videos."""

from pathlib import Path

from pipeline.ffmpeg_utils import (
    drawtext_font_prefix,
    escape_drawtext,
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


def ensure_shorts_format(input_path: Path, output_path: Path) -> Path:
    """Ensure video is 9:16, max 59s, H.264/AAC for Shorts compatibility."""
    run_ffmpeg([
        "-i", str(input_path),
        "-t", "59",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level", "4.0",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path),
    ])
    return output_path
