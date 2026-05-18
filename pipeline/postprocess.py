"""FFmpeg post-processing for rendered videos."""

import subprocess
from pathlib import Path


def add_text_overlay(input_path: Path, output_path: Path, caption: str) -> Path:
    """Burn caption text into the video."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", (
            f"drawtext=text='{caption}':"
            "fontcolor=white:fontsize=48:x=(w-text_w)/2:y=h-100:"
            "shadowcolor=black:shadowx=2:shadowy=2"
        ),
        "-c:a", "copy",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)
    return output_path


def add_background_music(video_path: Path, audio_path: Path, output_path: Path) -> Path:
    """Mix background music under video audio."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-filter_complex", "[1:a]volume=0.3[bg];[0:a][bg]amix=inputs=2[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)
    return output_path


def ensure_shorts_format(input_path: Path, output_path: Path) -> Path:
    """Ensure video is 9:16, max 59s, H.264/AAC for Shorts compatibility."""
    cmd = [
        "ffmpeg", "-y",
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
    ]
    subprocess.run(cmd, check=True)
    return output_path
