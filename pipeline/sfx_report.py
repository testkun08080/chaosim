"""Measure how well a concept's sound actually lands.

The question this answers is the one the ComfyUI backend raises: a Blender bake
knows the exact moment of every impact, generated footage does not. Rather than
assert that the cue-sheet-plus-onset approach is good enough, measure it, and
put the two backends side by side on the same numbers.

What is measured, and why each one can ruin a video on its own:

``onset_delta_ms``
    How far each cue moved to meet a measured visual onset. Large numbers mean
    the concept's predicted timing and the generated footage disagree — the
    sound will land off the picture. Zero for a Blender concept by construction,
    which is exactly the baseline worth comparing against.
``measured_ratio``
    Share of events whose time came from the footage rather than the cue sheet.
    A low ratio is not automatically wrong (a dark clip has few onsets) but it
    says the timing is a prediction, not an observation.
``generated_ratio``
    Share of cues voiced from the library or from generation, rather than
    falling through to a macOS system sound. On Linux the fallback is silence,
    so this being low means the video is quieter than it looks.
``polyphony_max``
    Most cues overlapping at once. High numbers are the "mud" failure: many
    impacts firing together read as one smeared noise.
``lufs``
    What the finished file actually came out at. ``ensure_shorts_format``
    targets -14 but falls back to dynamic normalisation on wide-range material,
    so this is measured, not assumed.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.audio_assets import (
    load_catalog,
    resolve_bgm,
    resolve_sfx_cues,
    load_sim_events,
)
from pipeline.ffmpeg_utils import get_duration
from pipeline.postprocess import measure_loudness
from pipeline.sfx_library import required_sounds

LOUDNESS_TARGET_LUFS = -14.0

CSV_FIELDS = [
    "slug", "source", "events", "cues", "thinned",
    "measured_ratio", "generated_ratio", "system_ratio",
    "onset_delta_median_ms", "onset_delta_p95_ms", "onset_delta_max_ms",
    "polyphony_max", "sounds_needed", "sounds_cached", "cache_hit_ratio",
    "lufs", "lufs_delta", "video",
]


def _percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile. Small samples here; no need for interpolation."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def onset_deltas_ms(events: list[dict]) -> list[float]:
    """How far each snapped event moved, in milliseconds.

    Only events that actually found an onset have a delta; ``cue_t`` is written
    by :func:`pipeline.sfx_events.snap_to_onsets` and is absent otherwise.
    """
    return [
        abs(float(e["t"]) - float(e["cue_t"])) * 1000.0
        for e in events
        if e.get("cue_t") is not None
    ]


def max_polyphony(cues: list[dict], window: float = 0.25) -> int:
    """Most cues sounding at once, treating each one-shot as ``window`` long.

    An approximation on purpose: the real length varies per file, and what this
    is for is spotting the pile-up, not measuring it to the millisecond.
    """
    starts = sorted(float(c.get("start", 0.0)) for c in cues)
    best = 0
    for index, start in enumerate(starts):
        overlapping = 1
        for later in starts[index + 1:]:
            if later - start >= window:
                break
            overlapping += 1
        best = max(best, overlapping)
    return best


def build_report(concept: dict, events: list[dict], cues: list[dict],
                 sounds: list[dict], video: Path | None) -> dict:
    """Assemble one concept's row. Pure — the CLI does the file I/O."""
    slug = concept.get("slug", "render")
    deltas = onset_deltas_ms(events)
    measured = sum(1 for e in events if e.get("source") == "onset")
    origins = [c.get("origin", "unknown") for c in cues]
    voiced = sum(1 for o in origins if o in ("library", "generated"))
    system = sum(1 for o in origins if o == "system")
    cached = sum(1 for s in sounds if s["cached"])

    loudness = measure_loudness(video) if video and video.is_file() else None
    lufs = None
    if loudness:
        try:
            lufs = round(float(loudness["output_i"]), 2)
        except (KeyError, TypeError, ValueError):
            lufs = None

    def ratio(count: int, total: int) -> float:
        return round(count / total, 3) if total else 0.0

    return {
        "slug": slug,
        "source": str(concept.get("source") or "blender"),
        "events": len(events),
        "cues": len(cues),
        # Events the polyphony limit merged away. A large number is not a bug —
        # it is the mud that would otherwise be in the mix.
        "thinned": max(0, len(events) - len(cues)),
        "measured_ratio": ratio(measured, len(events)),
        "generated_ratio": ratio(voiced, len(cues)),
        "system_ratio": ratio(system, len(cues)),
        "onset_delta_median_ms": round(_percentile(deltas, 0.5), 1),
        "onset_delta_p95_ms": round(_percentile(deltas, 0.95), 1),
        "onset_delta_max_ms": round(max(deltas), 1) if deltas else 0.0,
        "polyphony_max": max_polyphony(cues),
        "sounds_needed": len(sounds),
        "sounds_cached": cached,
        "cache_hit_ratio": ratio(cached, len(sounds)),
        "lufs": lufs,
        "lufs_delta": round(lufs - LOUDNESS_TARGET_LUFS, 2) if lufs is not None else None,
        "video": str(video) if video else "",
        "by_type": _by_type(cues),
    }


def _by_type(cues: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for cue in cues:
        key = str(cue.get("type") or "anchor")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def collect_concept(concept: dict, video_template: dict, settings: dict,
                    renders_dir: Path, final_dir: Path) -> dict:
    """Read one concept's artefacts off disk and report on them.

    Rebuilds the cues the compositor would build rather than reading them back
    from the video, so the report describes the same decisions the mix made.
    """
    slug = concept.get("slug", "render")
    sim_path = renders_dir / f"{slug}.mp4"
    final_path = final_dir / f"{slug}_final.mp4"

    events = load_sim_events(slug, renders_dir)
    # The compositor anchors cues against the concatenated base track; the sim
    # clip alone is enough to place them relative to each other, which is what
    # the timing numbers are about.
    base_segments = [{"role": "sim", "path": sim_path,
                      "duration": get_duration(sim_path) if sim_path.is_file() else 0.0}]
    cues = resolve_sfx_cues(concept, video_template, base_segments,
                            sim_events=events, settings=settings)
    sounds = required_sounds(load_catalog(), events)

    report = build_report(concept, events, cues, sounds,
                          final_path if final_path.is_file() else None)
    report["bgm"] = str(resolve_bgm(concept, video_template, settings) or "")
    return report


def summarise(rows: list[dict]) -> dict:
    """Totals across every concept in the report."""
    voiced = [r for r in rows if r["cues"]]
    return {
        "concepts": len(rows),
        "events": sum(r["events"] for r in rows),
        "cues": sum(r["cues"] for r in rows),
        # Having no events is fine (a pendulum hits nothing). Having events
        # and no cues is not: something was meant to be heard and is not.
        "silent_concepts": sum(1 for r in rows if r["events"] and not r["cues"]),
        "onset_delta_median_ms": round(
            _percentile([r["onset_delta_median_ms"] for r in voiced], 0.5), 1),
        "generated_ratio": round(
            sum(r["generated_ratio"] for r in voiced) / len(voiced), 3) if voiced else 0.0,
        "by_source": {
            src: sum(1 for r in rows if r["source"] == src)
            for src in sorted({r["source"] for r in rows})
        },
    }


def csv_rows(rows: list[dict]) -> list[dict]:
    """One flat row per concept, for spreadsheet review."""
    return [{field: row.get(field, "") for field in CSV_FIELDS} for row in rows]
