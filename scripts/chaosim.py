"""Main CLI for the Chaosim pipeline."""

import click
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from dotenv import load_dotenv

load_dotenv()
console = Console()


@click.group()
def cli():
    """Chaosim — Chaos Simulation Video Pipeline"""
    pass


@cli.command()
@click.option("--topic", required=True, help="Topic or simulation type to generate a concept for")
@click.option("--output-dir", default="concepts/generated", help="Output directory for concept YAML")
def plan(topic: str, output_dir: str):
    """Generate a video concept using Claude AI."""
    import anthropic
    import os
    from pipeline.planner import generate_concept, save_concept

    console.print(Panel(f"Generating concept for: [bold]{topic}[/bold]", style="cyan"))
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    concept = generate_concept(topic, client)
    path = save_concept(concept, Path(output_dir))
    console.print(f"[green]Concept saved:[/green] {path}")
    console.print(f"[bold]Title:[/bold] {concept.get('title')}")
    console.print(f"[bold]Hook:[/bold] {concept.get('hook')}")


@cli.command()
@click.argument("concept_file", type=click.Path(exists=True))
@click.option("--preset", default=None, help="Override render preset (preview/medium/high/ultra)")
def render(concept_file: str, preset: str | None):
    """Run Blender simulation and render for a concept file."""
    from pipeline.renderer import render_concept
    from pipeline.planner import load_concept

    concept_path = Path(concept_file)
    concept = load_concept(concept_path)
    console.print(Panel(f"Rendering: [bold]{concept.get('title')}[/bold]", style="yellow"))
    output = render_concept(concept, concept_path, Path("outputs/renders"), preset)
    console.print(f"[green]Rendered:[/green] {output}")


@cli.command()
@click.argument("concept_file", type=click.Path(exists=True))
@click.option("--upload", is_flag=True, help="Upload to YouTube after rendering")
@click.option("--preset", default=None, help="Override render preset")
def run(concept_file: str, upload: bool, preset: str | None):
    """Full pipeline: render + post-process (+ optional upload)."""
    from pipeline.workflow import run_full_pipeline

    concept_path = Path(concept_file)
    console.print(Panel(f"Running full pipeline: [bold]{concept_path.name}[/bold]", style="green"))
    final = run_full_pipeline(concept_path, upload=upload, render_preset=preset)
    console.print(f"[green]Complete:[/green] {final}")


@cli.command()
@click.argument("video_file", type=click.Path(exists=True))
@click.option("--concept", default=None, help="Concept YAML for metadata")
@click.option("--privacy", default="private", type=click.Choice(["private", "unlisted", "public"]))
def upload(video_file: str, concept: str | None, privacy: str):
    """Upload a video to YouTube."""
    from pipeline.uploader import upload_video
    from pipeline.planner import load_concept

    video_path = Path(video_file)
    concept_data = load_concept(Path(concept)) if concept else {"caption": video_path.stem}
    console.print(Panel(f"Uploading: [bold]{video_path.name}[/bold]", style="magenta"))
    url = upload_video(video_path, concept_data, privacy)
    console.print(f"[green]Uploaded:[/green] {url}")


@cli.command()
def list_concepts():
    """List all available concept files."""
    concepts_dir = Path("concepts")
    files = sorted(concepts_dir.glob("**/*.yaml"))
    console.print(Panel("Available Concepts", style="blue"))
    for f in files:
        console.print(f"  {f}")


if __name__ == "__main__":
    cli()
