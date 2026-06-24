"""Shared ffmpeg/ffprobe helpers.

Centralises binary resolution and stream probing so every stage uses the same
ffmpeg invocation. ffprobe is preferred when available, but all probing falls
back to parsing ``ffmpeg -i`` stderr so the pipeline works with ffmpeg alone.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path


def ffmpeg_bin() -> str:
    """Path to the ffmpeg binary (override with CHAOSIM_FFMPEG)."""
    return os.environ.get("CHAOSIM_FFMPEG", "ffmpeg")


def ffprobe_bin() -> str | None:
    """Path to ffprobe if available (override with CHAOSIM_FFPROBE)."""
    override = os.environ.get("CHAOSIM_FFPROBE")
    if override:
        return override
    return shutil.which("ffprobe")


def ffmpeg_available() -> bool:
    return shutil.which(ffmpeg_bin()) is not None or os.path.isfile(ffmpeg_bin())


def run_ffmpeg(args: list[str], quiet: bool = True) -> subprocess.CompletedProcess:
    """Run ffmpeg with ``-y`` and the resolved binary. Raises on failure."""
    cmd = [ffmpeg_bin(), "-y"]
    if quiet:
        cmd += ["-hide_banner", "-loglevel", "error"]
    cmd += args
    return subprocess.run(cmd, check=True)


def _ffmpeg_inspect(path: Path) -> str:
    """Return ffmpeg's stderr describing the input (used for probing)."""
    proc = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
    )
    # ffmpeg exits non-zero when no output is specified; stderr holds the info.
    return proc.stderr


def has_audio_stream(path: Path) -> bool:
    """True if the media file contains at least one audio stream."""
    probe = ffprobe_bin()
    if probe:
        proc = subprocess.run(
            [probe, "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True,
        )
        return bool(proc.stdout.strip())
    return bool(re.search(r"Stream #\d+:\d+.*: Audio:", _ffmpeg_inspect(path)))


def get_duration(path: Path) -> float:
    """Duration of a media file in seconds (0.0 if it cannot be determined)."""
    probe = ffprobe_bin()
    if probe:
        proc = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True,
        )
        try:
            return float(proc.stdout.strip())
        except (ValueError, TypeError):
            return 0.0
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", _ffmpeg_inspect(path))
    if not m:
        return 0.0
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def get_resolution(path: Path) -> tuple[int, int] | None:
    """(width, height) of the first video stream, or None."""
    probe = ffprobe_bin()
    if probe:
        proc = subprocess.run(
            [probe, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
            capture_output=True, text=True,
        )
        m = re.match(r"(\d+)x(\d+)", proc.stdout.strip())
        if m:
            return int(m.group(1)), int(m.group(2))
        return None
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", _ffmpeg_inspect(path))
    return (int(m.group(1)), int(m.group(2))) if m else None


_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
]


def drawtext_fontfile() -> str | None:
    """Path to a (Japanese-capable) font for drawtext, or None for fontconfig.

    Override with CHAOSIM_FONT. Falls back to common CJK fonts so Japanese
    captions render correctly; returns None to let ffmpeg pick via fontconfig.
    """
    override = os.environ.get("CHAOSIM_FONT")
    if override and os.path.isfile(override):
        return override
    for candidate in _FONT_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    return None


def drawtext_font_prefix() -> str:
    """``fontfile='...':`` prefix for a drawtext filter (empty if none found)."""
    font = drawtext_fontfile()
    return f"fontfile='{font}':" if font else ""


def escape_drawtext(text: str) -> str:
    """Escape text for use inside an ffmpeg drawtext ``text='...'`` value."""
    if text is None:
        return ""
    out = str(text)
    out = out.replace("\\", "\\\\")
    out = out.replace(":", r"\:")
    out = out.replace("'", r"\'")
    out = out.replace("%", r"\%")
    out = out.replace("\n", " ")
    return out
