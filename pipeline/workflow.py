"""End-to-end pipeline orchestrator."""

from pathlib import Path
import anthropic
import os
from dotenv import load_dotenv

from pipeline.planner import generate_concept, save_concept, load_concept
from pipeline.renderer import render_concept
from pipeline.postprocess import ensure_shorts_format
from pipeline.uploader import upload_video

load_dotenv()


def run_full_pipeline(concept_path: Path, upload: bool = False, render_preset: str | None = None):
    """Execute the complete pipeline for a concept file."""
    concept = load_concept(concept_path)
    slug = concept.get("slug", "render")

    renders_dir = Path("outputs/renders")
    final_dir = Path("outputs/final")
    final_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Rendering: {concept.get('title')} ===")
    raw_video = render_concept(concept, concept_path, renders_dir, render_preset)

    print(f"\n=== Post-processing ===")
    final_video = final_dir / f"{slug}_final.mp4"
    ensure_shorts_format(raw_video, final_video)

    print(f"\n=== Output: {final_video} ===")

    if upload:
        print(f"\n=== Uploading to YouTube ===")
        url = upload_video(final_video, concept)
        print(f"Live at: {url}")

    return final_video


def plan_and_run(topic: str, upload: bool = False):
    """Generate concept from topic, then run full pipeline."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print(f"\n=== Generating concept for: {topic} ===")
    concept = generate_concept(topic, client)
    concept_path = save_concept(concept, Path("concepts/generated"))
    print(f"Concept saved: {concept_path}")

    return run_full_pipeline(concept_path, upload=upload)
