"""Japanese narration via the VOICEVOX HTTP API (with a silent-track stub)."""

import json
import os
import wave
from pathlib import Path

import requests

from pipeline.config import stub_mode
from pipeline.ffmpeg_utils import get_duration, run_ffmpeg

DEFAULT_URL = "http://localhost:50021"


def voicevox_url(settings: dict | None = None) -> str:
    if settings:
        url = settings.get("voicevox", {}).get("url")
        if url:
            return url
    return os.environ.get("VOICEVOX_URL", DEFAULT_URL)


def voicevox_available(settings: dict | None = None, timeout: float = 1.5) -> bool:
    if stub_mode():
        return False
    try:
        r = requests.get(f"{voicevox_url(settings)}/version", timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False


def synthesize_line(text: str, speaker: int, out_wav: Path, speed: float = 1.0,
                    pitch: float = 0.0, intonation: float = 1.0,
                    settings: dict | None = None) -> Path:
    """Synthesize a single line to a WAV file using VOICEVOX's 2-step API."""
    base = voicevox_url(settings)
    q = requests.post(f"{base}/audio_query", params={"text": text, "speaker": speaker},
                      timeout=30)
    q.raise_for_status()
    query = q.json()
    query["speedScale"] = speed
    query["pitchScale"] = pitch
    query["intonationScale"] = intonation
    query["outputSamplingRate"] = 24000

    s = requests.post(f"{base}/synthesis", params={"speaker": speaker},
                      headers={"Content-Type": "application/json"},
                      data=json.dumps(query), timeout=120)
    s.raise_for_status()
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    out_wav.write_bytes(s.content)
    return out_wav


def _wav_duration(path: Path, fallback: float) -> float:
    try:
        with wave.open(str(path), "rb") as w:
            frames, rate = w.getnframes(), w.getframerate()
            if rate:
                return frames / float(rate)
    except (wave.Error, EOFError, FileNotFoundError):
        pass
    dur = get_duration(path)
    return dur if dur > 0 else fallback


def _estimate_seconds(text: str, settings: dict | None) -> float:
    per_char = 0.18
    if settings:
        per_char = settings.get("narration", {}).get("estimate_sec_per_char", per_char)
    return max(2.0, len(text) * per_char)


def _silent_wav(out_wav: Path, duration: float) -> Path:
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=24000",
        "-t", f"{duration:.3f}", str(out_wav),
    ])
    return out_wav


def _concat_wavs(parts: list[Path], out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if len(parts) == 1:
        run_ffmpeg(["-i", str(parts[0]), "-ar", "24000", "-ac", "1", str(out_path)])
        return out_path
    list_file = out_path.parent / f"{out_path.stem}_concat.txt"
    list_file.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    run_ffmpeg([
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-ar", "24000", "-ac", "1", str(out_path),
    ])
    list_file.unlink(missing_ok=True)
    return out_path


def synthesize_script(lines, speaker: int, out_path: Path, speed: float = 1.0,
                      pitch: float = 0.0, settings: dict | None = None) -> tuple[Path, list[dict]]:
    """Synthesize a narration script to one audio file plus per-line timings.

    Returns (audio_path, segments) where segments = [{text, start, end}], used
    for caption synchronisation. Falls back to a silent track of estimated
    length when VOICEVOX is unavailable.
    """
    if isinstance(lines, str):
        lines = [ln.strip() for ln in lines.splitlines() if ln.strip()]
    lines = [ln for ln in (lines or []) if ln and str(ln).strip()]

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not lines:
        _silent_wav(out_path, 1.0)
        return out_path, []

    use_real = voicevox_available(settings)
    if use_real:
        print(f"  VOICEVOX available at {voicevox_url(settings)}")
    else:
        print("  VOICEVOX unavailable — synthesizing silent placeholder audio")
    parts: list[Path] = []
    segments: list[dict] = []
    cursor = 0.0
    work = out_path.parent / f"_narr_{out_path.stem}"
    work.mkdir(parents=True, exist_ok=True)

    for i, line in enumerate(lines):
        part = work / f"line_{i:02d}.wav"
        if use_real:
            try:
                synthesize_line(line, speaker, part, speed=speed, pitch=pitch, settings=settings)
            except requests.RequestException as exc:
                print(f"  VOICEVOX failed on line {i}: {exc}; using silence")
                _silent_wav(part, _estimate_seconds(line, settings))
        else:
            _silent_wav(part, _estimate_seconds(line, settings))
        dur = _wav_duration(part, _estimate_seconds(line, settings))
        segments.append({"text": line, "start": round(cursor, 3), "end": round(cursor + dur, 3)})
        cursor += dur
        parts.append(part)

    _concat_wavs(parts, out_path)
    for p in parts:
        p.unlink(missing_ok=True)
    work.rmdir() if not any(work.iterdir()) else None
    return out_path, segments
