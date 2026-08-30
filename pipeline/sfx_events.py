"""Timed SFX events: the contract both render backends must satisfy.

``outputs/renders/<slug>_events.json`` is what makes a rendered clip scorable
by the compositor. Blender writes it from the same bake it renders, so its
times are exact. Generated footage has no bake, so we build the same file from
two weaker sources and say which one each event came from:

* **cue sheet** — the concept declares what happens when, per shot. Known up
  front because the shot lengths are ours to choose.
* **onset** — after the clip exists, the frames themselves are measured and
  each cue is snapped to the nearest visual change.

The point of ``docs/sfx-design.md`` is that timing is never typed in by hand.
A cue sheet is a *prediction*; the onset pass is what turns it into a
measurement, and ``source`` records which one survived so the accuracy of the
generative path can be reported rather than assumed.

Schema of one event (``docs/sfx-design.md`` 3-1)::

    {"t": 2.35, "type": "impact", "intensity": 0.82, "object": "shot_02",
     "source": "onset"}
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from pipeline.ffmpeg_utils import ffmpeg_bin

# type -> the role the audio catalog resolves it through.
EVENT_TYPES = ("impact", "drop", "collapse", "whoosh", "settle", "tick")
DEFAULT_TYPE = "impact"

# How far a cue may be moved to meet a measured onset. Wider than this and the
# onset is more likely a different event than the one the cue described.
SNAP_WINDOW_SEC = 0.35


def normalize_event(raw: dict, offset: float = 0.0, default_object: str = "") -> dict:
    """One cue -> the canonical event shape, with ``t`` shifted onto the timeline."""
    event_type = str(raw.get("type") or DEFAULT_TYPE)
    if event_type not in EVENT_TYPES:
        event_type = DEFAULT_TYPE
    intensity = raw.get("intensity")
    try:
        intensity = min(1.0, max(0.0, float(intensity)))
    except (TypeError, ValueError):
        intensity = 0.6
    return {
        "t": round(float(raw.get("t", 0.0)) + offset, 3),
        "type": event_type,
        "intensity": round(intensity, 3),
        "object": str(raw.get("object") or default_object),
        "source": str(raw.get("source") or "cue"),
    }


def cue_sheet_events(shots: list[dict]) -> list[dict]:
    """Flatten per-shot cues (relative seconds) onto the concatenated timeline.

    ``shots`` entries need ``duration``; each cue's ``t`` is relative to the
    start of its own shot. A cue past the end of its shot is dropped, because
    a shot that was shortened (a cost guard, or a model that returned less)
    would otherwise fire its sound over the *next* shot.
    """
    events: list[dict] = []
    cursor = 0.0
    for index, shot in enumerate(shots or [], start=1):
        duration = float(shot.get("duration") or 0.0)
        name = str(shot.get("name") or f"shot_{index:02d}")
        for cue in shot.get("cues") or []:
            t = float(cue.get("t", 0.0))
            if duration and t > duration:
                continue
            events.append(normalize_event(cue, offset=cursor, default_object=name))
        cursor += duration
    events.sort(key=lambda e: e["t"])
    return events


def detect_onsets(video: Path, threshold: float = 0.12) -> list[float]:
    """Times (seconds) where the picture changes sharply.

    Uses ffmpeg's own scene score, so there is no extra dependency. Returns an
    empty list when ffmpeg cannot read the file rather than raising — a missing
    onset pass must degrade to the cue sheet, not break the render.
    """
    cmd = [
        ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(video),
        "-filter_complex", f"select='gt(scene,{threshold})',metadata=print:file=-",
        "-f", "null", "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired):
        return []
    times = [float(m.group(1)) for m in re.finditer(r"pts_time:([0-9.]+)", proc.stdout)]
    return sorted(set(times))


def snap_to_onsets(events: list[dict], onsets: list[float],
                   window: float = SNAP_WINDOW_SEC) -> list[dict]:
    """Move each cue to the nearest measured onset within ``window``.

    An event with no onset nearby keeps its predicted time and stays
    ``source: "cue"`` — that is the honest label, and ``sfx-report`` counts it.
    Each onset is consumed at most once so two cues cannot collapse onto the
    same frame.
    """
    if not onsets:
        return [dict(e) for e in events]

    remaining = sorted(onsets)
    snapped: list[dict] = []
    for event in sorted(events, key=lambda e: e["t"]):
        out = dict(event)
        best, best_delta = None, window
        for onset in remaining:
            delta = abs(onset - event["t"])
            if delta <= best_delta:
                best, best_delta = onset, delta
            elif onset > event["t"]:
                break  # sorted: everything further out is worse
        if best is not None:
            remaining.remove(best)
            out["t"] = round(best, 3)
            out["source"] = "onset"
            out["cue_t"] = round(event["t"], 3)
        snapped.append(out)
    snapped.sort(key=lambda e: e["t"])
    return snapped


def write_events(path: Path, events: list[dict], meta: dict | None = None) -> Path:
    """Write the sidecar the compositor reads.

    ``load_sim_events`` accepts either a bare list or ``{"events": [...]}``;
    the dict form is used here so the extra measurement metadata has somewhere
    to live without changing that reader.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"events": events}
    if meta:
        payload.update(meta)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
