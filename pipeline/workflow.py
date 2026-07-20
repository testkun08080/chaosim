"""End-to-end pipeline orchestrator.

Stages: plan -> sim (Blender) -> material (HyperFrames) -> narration (VOICEVOX)
-> compose -> thumbnail -> upload. Each external tool degrades to an ffmpeg
stub when unavailable (or under CHAOSIM_STUB=1 / preview mode), so the whole
pipeline runs with only ffmpeg installed.
"""

import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from pipeline import hyperframes
from pipeline.compositor import compose
from pipeline.config import load_settings
from pipeline.narration import synthesize_script
from pipeline.planner import generate_concept, load_concept, normalize_concept, save_concept
from pipeline.renderer import render_concept
from pipeline.templating import build_context, load_video_template, render_template
from pipeline.thumbnail import generate_thumbnail

load_dotenv()

ALL_STAGES = {"sim", "material", "narration", "compose", "thumb"}

RENDERS_DIR = Path("outputs/renders")
MATERIAL_DIR = Path("outputs/material")
AUDIO_DIR = Path("outputs/audio")
WORK_DIR = Path("outputs/work")
FINAL_DIR = Path("outputs/final")


# --- individual stages -----------------------------------------------------

def stage_sim(concept: dict, concept_path: Path, render_preset: str | None) -> Path:
    print("\n=== [1/6] Simulation footage ===")
    return render_concept(concept, concept_path, RENDERS_DIR, render_preset)


def stage_narration(concept: dict, video_template: dict, settings: dict) -> tuple[Path | None, list[dict]]:
    print("\n=== [3/6] Narration (VOICEVOX) ===")
    lines = _narration_lines(concept, video_template, settings)
    if not lines:
        print("  (narration disabled / no lines)")
        return None, []
    narr = concept.get("narration", {})
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    out = AUDIO_DIR / f"{concept.get('slug', 'render')}_narration.wav"
    path, segments = synthesize_script(
        lines, speaker=narr.get("speaker", 3), out_path=out,
        speed=narr.get("speed", 1.0), pitch=narr.get("pitch", 0.0), settings=settings,
    )
    print(f"  narration: {path} ({len(segments)} lines)")
    return path, segments


def stage_material(concept: dict, video_template: dict, settings: dict,
                   sim_path: Path) -> tuple[list[dict], list[dict]]:
    """Render HyperFrames material; return (base_segments, overlay_segments)."""
    print("\n=== [2/6] Video material (HyperFrames) ===")
    slug = concept.get("slug", "render")
    mat_dir = MATERIAL_DIR / slug
    base_segments: list[dict] = []
    overlay_segments: list[dict] = []

    for i, seg in enumerate(concept.get("segments", [])):
        role = seg.get("role", "")
        track = seg.get("track", "base")
        template = seg.get("template")

        if role == "sim":
            base_segments.append({"role": "sim", "path": sim_path})
            continue

        if track == "base" and template:
            out = mat_dir / f"{i:02d}_{role}.mp4"
            hyperframes.render_segment_from_template(
                template, concept, settings, out,
                video_template=video_template, segment_cfg=seg, transparent=False,
            )
            base_segments.append({"role": role, "path": out})
            print(f"  base: {role} -> {out}")
        elif track == "overlay" and template:
            if seg.get("from") == "narration":
                continue  # realised as burned captions in compose
            if "start" not in seg:
                continue
            ext = "webm" if seg.get("transparent") else "mp4"
            out = mat_dir / f"{i:02d}_{role}.{ext}"
            hyperframes.render_segment_from_template(
                template, concept, settings, out,
                video_template=video_template, segment_cfg=seg,
                transparent=bool(seg.get("transparent")),
            )
            overlay_segments.append({"path": out, "start": float(seg["start"]),
                                     "duration": float(seg.get("duration", 3.0))})
            print(f"  overlay: {role} @ {seg['start']}s -> {out}")

    return base_segments, overlay_segments


def stage_compose(concept: dict, video_template: dict, settings: dict,
                  base_segments: list[dict], overlay_segments: list[dict],
                  narration_path: Path | None, narration_segments: list[dict]) -> Path:
    print("\n=== [4/6] Compositing ===")
    from pipeline.audio_assets import load_sim_events, resolve_bgm, resolve_sfx_cues

    slug = concept.get("slug", "render")
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    final = FINAL_DIR / f"{slug}_final.mp4"

    bgm_path = resolve_bgm(concept, video_template, settings)
    if bgm_path:
        print(f"  bgm: {bgm_path}")
    else:
        print("  bgm: (none)")

    sim_events = load_sim_events(slug, RENDERS_DIR)
    sfx_cues = resolve_sfx_cues(
        concept, video_template, base_segments, sim_events=sim_events, settings=settings,
    )
    print(f"  sfx cues: {len(sfx_cues)} (sim_events={len(sim_events)})")

    return compose(
        concept, video_template, base_segments, overlay_segments,
        narration_path, narration_segments, bgm_path, settings,
        out_path=final, work_dir=WORK_DIR / slug, sfx_cues=sfx_cues,
    )


def stage_thumbnail(concept: dict, video_template: dict, settings: dict,
                    source_video: Path | None) -> Path:
    print("\n=== [5/6] Thumbnail ===")
    slug = concept.get("slug", "render")
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    out = FINAL_DIR / f"{slug}_thumb.png"
    thumb = generate_thumbnail(concept, settings, out, video_template=video_template,
                               source_video=source_video)
    print(f"  thumbnail: {thumb}")
    return thumb


# --- helpers ---------------------------------------------------------------

def _narration_lines(concept: dict, video_template: dict, settings: dict) -> list[str]:
    narr = concept.get("narration", {}) or {}
    if narr.get("enabled") is False:
        return []
    lines = [l for l in (narr.get("lines") or []) if str(l).strip()]
    if lines:
        return lines
    source = narr.get("source", "default")
    try:
        ctx = build_context(concept, settings, video_template=video_template)
        text = render_template("narration", source, ctx)
        return [l.strip() for l in text.splitlines() if l.strip()]
    except Exception:  # noqa: BLE001
        return []


# --- top-level orchestration ----------------------------------------------

def run_full_pipeline(concept_path: Path, upload: bool = False,
                      render_preset: str | None = None, stages: set[str] | None = None,
                      privacy: str = "private", preview: bool = False) -> Path:
    """Execute the complete pipeline for a concept file."""
    if preview:
        os.environ["CHAOSIM_STUB"] = "1"
    stages = stages or set(ALL_STAGES)

    concept = normalize_concept(load_concept(concept_path))
    settings = load_settings()
    video_template = load_video_template(concept["video_template"])
    slug = concept.get("slug", "render")

    print(f"\n=== Pipeline: {concept.get('title')} (template={concept['video_template']}) ===")
    from pipeline.renderer import blender_available
    from pipeline.hyperframes import hyperframes_available
    from pipeline.narration import voicevox_available
    print(f"  tools: blender={blender_available()} "
          f"hyperframes={hyperframes_available()} "
          f"voicevox={voicevox_available(settings)} "
          f"stub={preview or os.environ.get('CHAOSIM_STUB')}")

    # 1. Simulation footage.
    sim_path = RENDERS_DIR / f"{slug}.mp4"
    if "sim" in stages or not sim_path.exists():
        sim_path = stage_sim(concept, concept_path, render_preset)

    # 2. Narration (needed for captions during compose).
    narration_path, narration_segments = (None, [])
    if "narration" in stages:
        narration_path, narration_segments = stage_narration(concept, video_template, settings)

    # 3. HyperFrames material (intro/outro/overlays).
    base_segments, overlay_segments = stage_material(concept, video_template, settings, sim_path)

    # 4. Compose.
    final_video = FINAL_DIR / f"{slug}_final.mp4"
    if "compose" in stages:
        final_video = stage_compose(concept, video_template, settings, base_segments,
                                    overlay_segments, narration_path, narration_segments)
        print(f"\n=== Output: {final_video} ===")

    # 5. Thumbnail.
    thumb = None
    if "thumb" in stages:
        thumb = stage_thumbnail(concept, video_template, settings,
                                source_video=final_video if final_video.exists() else sim_path)

    # 6. Upload.
    if upload:
        from pipeline.uploader import upload_video  # lazy: avoids google deps unless uploading
        print("\n=== [6/6] Uploading to YouTube ===")
        url = upload_video(final_video, concept, privacy, thumbnail_path=thumb)
        print(f"Live at: {url}")

    return final_video


def plan_and_run(topic: str, upload: bool = False, preview: bool = False) -> Path:
    """Generate concept from topic, then run full pipeline."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print(f"\n=== Generating concept for: {topic} ===")
    concept = generate_concept(topic, client)
    concept_path = save_concept(concept, Path("concepts/generated"))
    print(f"Concept saved: {concept_path}")

    return run_full_pipeline(concept_path, upload=upload, preview=preview)
