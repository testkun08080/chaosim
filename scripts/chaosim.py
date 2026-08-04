"""Main CLI for the Chaosim pipeline."""

import sys
from pathlib import Path

# Ensure the repo root is importable when run as `python scripts/chaosim.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import click
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
@click.option("--local", "local_mode", is_flag=True,
              help="Skip Claude API and write a ready-to-render local concept (domino chain)")
def plan(topic: str, output_dir: str, local_mode: bool):
    """Generate a video concept using Claude AI (or a local template)."""
    import os
    from pipeline.planner import generate_concept, save_concept, build_local_concept

    console.print(Panel(f"Generating concept for: [bold]{topic}[/bold]", style="cyan"))
    if local_mode or not os.environ.get("ANTHROPIC_API_KEY"):
        if not local_mode:
            console.print("[yellow]ANTHROPIC_API_KEY missing — using local concept template[/yellow]")
        concept = build_local_concept(topic)
    else:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        concept = generate_concept(topic, client)
    path = save_concept(concept, Path(output_dir))
    console.print(f"[green]Concept saved:[/green] {path}")
    console.print(f"[bold]Title:[/bold] {concept.get('title')}")
    console.print(f"[bold]Hook:[/bold] {concept.get('hook')}")
    console.print(f"[bold]Scene:[/bold] {concept.get('scene_script')}")


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
def material(concept_file: str):
    """Render HyperFrames video material (intro/overlays/outro) for a concept."""
    from pipeline.config import load_settings
    from pipeline.planner import load_concept, normalize_concept
    from pipeline.templating import load_video_template
    from pipeline.workflow import stage_material

    concept = normalize_concept(load_concept(Path(concept_file)))
    settings = load_settings()
    vt = load_video_template(concept["video_template"])
    sim_path = Path("outputs/renders") / f"{concept.get('slug', 'render')}.mp4"
    console.print(Panel(f"Material: [bold]{concept.get('title')}[/bold]", style="cyan"))
    base, overlays = stage_material(concept, vt, settings, sim_path)
    console.print(f"[green]Material done:[/green] {len(base)} base, {len(overlays)} overlay clips")


@cli.command()
@click.argument("concept_file", type=click.Path(exists=True))
@click.option("--speaker", default=None, type=int, help="Override VOICEVOX speaker id")
@click.option("--speed", default=None, type=float, help="Override narration speed")
def narrate(concept_file: str, speaker: int | None, speed: float | None):
    """Generate Japanese narration audio (VOICEVOX) for a concept."""
    from pipeline.config import load_settings
    from pipeline.planner import load_concept, normalize_concept
    from pipeline.templating import load_video_template
    from pipeline.workflow import stage_narration

    concept = normalize_concept(load_concept(Path(concept_file)))
    if speaker is not None:
        concept["narration"]["speaker"] = speaker
    if speed is not None:
        concept["narration"]["speed"] = speed
    settings = load_settings()
    vt = load_video_template(concept["video_template"])
    console.print(Panel(f"Narration: [bold]{concept.get('title')}[/bold]", style="cyan"))
    path, segments = stage_narration(concept, vt, settings)
    console.print(f"[green]Narration:[/green] {path} ({len(segments)} lines)")


@cli.command()
@click.argument("concept_file", type=click.Path(exists=True))
@click.option("--preview", is_flag=True, help="Force stub mode (no Blender/HyperFrames/VOICEVOX)")
def compose(concept_file: str, preview: bool):
    """Build the final composited video (sim + material + narration + captions)."""
    from pipeline.workflow import run_full_pipeline

    console.print(Panel(f"Composing: [bold]{Path(concept_file).name}[/bold]", style="green"))
    final = run_full_pipeline(Path(concept_file), stages={"sim", "material", "narration", "compose"},
                              preview=preview)
    console.print(f"[green]Composed:[/green] {final}")


@cli.command()
@click.argument("concept_file", type=click.Path(exists=True))
def thumbnail(concept_file: str):
    """Generate a YouTube thumbnail PNG for a concept."""
    from pipeline.config import load_settings
    from pipeline.planner import load_concept, normalize_concept
    from pipeline.templating import load_video_template
    from pipeline.workflow import stage_thumbnail

    concept = normalize_concept(load_concept(Path(concept_file)))
    settings = load_settings()
    vt = load_video_template(concept["video_template"])
    slug = concept.get("slug", "render")
    final = Path("outputs/final") / f"{slug}_final.mp4"
    sim = Path("outputs/renders") / f"{slug}.mp4"
    source = final if final.exists() else (sim if sim.exists() else None)
    console.print(Panel(f"Thumbnail: [bold]{concept.get('title')}[/bold]", style="cyan"))
    out = stage_thumbnail(concept, vt, settings, source_video=source)
    console.print(f"[green]Thumbnail:[/green] {out}")


@cli.command()
@click.argument("concept_file", type=click.Path(exists=True))
@click.option("--upload", is_flag=True, help="Upload to YouTube after rendering")
@click.option("--preset", default=None, help="Override render preset")
@click.option("--stages", default="all",
              help="Comma list of stages to run: sim,material,narration,compose,thumb (or 'all')")
@click.option("--preview", is_flag=True, help="Force stub mode (no heavy external deps)")
@click.option("--privacy", default="private", type=click.Choice(["private", "unlisted", "public"]))
def run(concept_file: str, upload: bool, preset: str | None, stages: str,
        preview: bool, privacy: str):
    """Full pipeline: sim + material + narration + compose + thumbnail (+ optional upload)."""
    from pipeline.workflow import run_full_pipeline, ALL_STAGES

    stage_set = set(ALL_STAGES) if stages.strip() == "all" else {
        s.strip() for s in stages.split(",") if s.strip()
    }
    concept_path = Path(concept_file)
    console.print(Panel(f"Running full pipeline: [bold]{concept_path.name}[/bold]", style="green"))
    final = run_full_pipeline(concept_path, upload=upload, render_preset=preset,
                              stages=stage_set, privacy=privacy, preview=preview)
    console.print(f"[green]Complete:[/green] {final}")


@cli.command()
@click.argument("video_file", type=click.Path(exists=True))
@click.option("--concept", default=None, type=click.Path(exists=True),
              help="Concept YAML for metadata")
@click.option("--thumbnail", "thumbnail_file", default=None, type=click.Path(exists=True),
              help="Thumbnail PNG to set on the uploaded video")
@click.option("--privacy", default="private", type=click.Choice(["private", "unlisted", "public"]))
@click.option("--run-url", default=None, help="CI run URL, appended to the video description")
@click.option("--record-dir", default=None,
              help="Write an upload receipt JSON here (default: settings output.uploads_dir)")
@click.option("--record-slug", default=None,
              help="Name the receipt file explicitly (default: the concept's slug)")
@click.option("--dry-run", is_flag=True,
              help="Authenticate and build the request body, but do not upload")
def upload(video_file: str, concept: str | None, thumbnail_file: str | None, privacy: str,
           run_url: str | None, record_dir: str | None, record_slug: str | None,
           dry_run: bool):
    """Upload a video to YouTube (privacyStatus=private is YouTube's closest thing to a draft)."""
    from pipeline.config import load_settings
    from pipeline.planner import load_concept, normalize_concept
    from pipeline.uploader import (build_video_body, get_authenticated_service, upload_video,
                                   write_upload_record)

    video_path = Path(video_file)
    # normalize_concept matches what `run --upload` feeds the uploader.
    concept_data = (normalize_concept(load_concept(Path(concept))) if concept
                    else {"caption": video_path.stem})
    # The caller may pin the receipt name so it cannot drift from the identity
    # the caller already validated (upload.yml reads back outputs/uploads/<slug>.json).
    slug = record_slug or concept_data.get("slug") or video_path.stem
    extra = f"Built by GitHub Actions: {run_url}" if run_url else ""

    console.print(Panel(f"Uploading: [bold]{video_path.name}[/bold]", style="magenta"))

    # A credential problem is an operator error, not a bug — report it as a one-line
    # message rather than a traceback, since CI logs surface only the tail.
    try:
        if dry_run:
            body = build_video_body(concept_data, privacy, fallback_title=video_path.stem,
                                    extra_description=extra)
            get_authenticated_service()   # prove credentials work without spending quota
            console.print("[yellow]--dry-run:[/yellow] credentials OK, not uploading")
            console.print(f"[bold]Title:[/bold] {body['snippet']['title']}")
            console.print(f"[bold]Tags:[/bold] {', '.join(body['snippet']['tags'])}")
            console.print(f"[bold]Privacy:[/bold] {body['status']['privacyStatus']}")
            return

        result = upload_video(video_path, concept_data, privacy,
                              thumbnail_path=Path(thumbnail_file) if thumbnail_file else None,
                              extra_description=extra)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    target = record_dir or load_settings().get("output", {}).get("uploads_dir", "outputs/uploads")
    record = write_upload_record(Path(target), slug, result, source_video=str(video_path),
                                 concept_path=concept, run_url=run_url)
    console.print(f"[green]Uploaded:[/green] {result['url']}")
    console.print(f"[green]Record:[/green] {record}")


@cli.command("youtube-auth")
@click.option("--client-secret", "client_secret_file", default=None, type=click.Path(exists=True),
              help="OAuth client secret JSON (default: $YOUTUBE_CLIENT_SECRET_PATH)")
def youtube_auth(client_secret_file: str | None):
    """Mint a YouTube refresh token for CI. Run this locally — it opens a browser."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    from pipeline.uploader import SCOPES, client_secret_path

    secret = Path(client_secret_file) if client_secret_file else client_secret_path()
    if not secret.exists():
        raise click.ClickException(
            f"OAuth client secret not found at {secret}. Create an OAuth client of type "
            "'Desktop app' in Google Cloud Console and download the JSON."
        )

    console.print(Panel("Opening browser for YouTube consent…", style="magenta"))
    flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
    # prompt='consent' is required: without it Google omits refresh_token on re-authorization.
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    if not creds.refresh_token:
        raise click.ClickException(
            "Google returned no refresh token. Revoke this app at "
            "https://myaccount.google.com/permissions and try again."
        )

    console.print("\n[green]Store these as GitHub secrets (environment: youtube):[/green]\n")
    for name, value in (("YOUTUBE_CLIENT_ID", creds.client_id),
                        ("YOUTUBE_CLIENT_SECRET", creds.client_secret),
                        ("YOUTUBE_REFRESH_TOKEN", creds.refresh_token)):
        click.echo(f"{name}={value}")
    console.print(
        "\n[yellow]Note:[/yellow] a token minted while the OAuth consent screen is in "
        "'Testing' expires after 7 days. Publish the app to 'In Production' first."
    )


@cli.command()
def list_concepts():
    """List all available concept files."""
    concepts_dir = Path("concepts")
    files = sorted(concepts_dir.glob("**/*.yaml"))
    console.print(Panel("Available Concepts", style="blue"))
    for f in files:
        console.print(f"  {f}")


@cli.command()
@click.option("--output", default="docs/catalog/README.md", show_default=True,
              help="Where to write the generated view.")
@click.option("--data-dir", default="outputs/catalog", show_default=True,
              help="Where to write catalog.json / concepts.csv.")
@click.option("--no-data", is_flag=True, help="Skip the JSON/CSV data files.")
@click.option("--check", is_flag=True,
              help="Exit non-zero if any concept has an error-level finding.")
@click.option("--stdout", "to_stdout", is_flag=True, help="Print instead of writing the file.")
def catalog(output, data_dir, no_data, check, to_stdout):
    """Cross-check concepts against scene scripts and write docs/catalog/."""
    from pipeline.catalog import CSV_FIELDS, catalog_csv_rows, collect_catalog
    from pipeline.report import write_csv, write_json
    from pipeline.templating import render_template

    ctx = collect_catalog()
    markdown = render_template("docs", "catalog", ctx)

    if to_stdout:
        click.echo(markdown)
    else:
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
        console.print(f"[green]Wrote[/green] {out}")

    if not no_data:
        d = Path(data_dir)
        write_json(d / "catalog.json", ctx)
        write_csv(d / "concepts.csv", catalog_csv_rows(ctx), CSV_FIELDS)
        console.print(f"[green]Wrote[/green] {d / 'catalog.json'}, {d / 'concepts.csv'}")

    t = ctx["totals"]
    console.print(
        f"{t['concepts']} concepts · [red]{t['errors']} error[/red] · "
        f"[yellow]{t['warnings']} warn[/yellow] · "
        f"params {t['params_live']}/{t['params_declared']} ({t['params_live_pct']}%) reach code"
    )
    for e in ctx["entries"]:
        for f in e["findings"]:
            if f["level"] == "error":
                console.print(f"  [red]error[/red] {e['slug']}: {f['message']}")

    if check and t["errors"]:
        raise SystemExit(1)


@cli.command("gate1-report")
@click.option("--gate1-dir", default="docs/gate1", show_default=True,
              help="Directory `gate-review` collected contact sheets into.")
@click.option("--data-dir", default="outputs/gate1", show_default=True,
              help="Where to write gate1.json / gate1.csv.")
@click.option("--check", is_flag=True,
              help="Exit non-zero if any concept is still pending a verdict.")
def gate1_report(gate1_dir, data_dir, check):
    """Turn docs/gate1/ + verdicts.yaml into outputs/gate1/ data files."""
    from pipeline.gate1 import CSV_FIELDS, collect_gate1, gate1_csv_rows, load_verdicts
    from pipeline.report import write_csv, write_json

    g1 = Path(gate1_dir)
    record = collect_gate1(g1, load_verdicts(g1 / "verdicts.yaml"))

    d = Path(data_dir)
    write_json(d / "gate1.json", record)
    write_csv(d / "gate1.csv", gate1_csv_rows(record), CSV_FIELDS)
    console.print(f"[green]Wrote[/green] {d / 'gate1.json'}, {d / 'gate1.csv'}")

    t = record["totals"]
    console.print(
        f"{t['concepts']} concepts · contact sheet {t['with_contact_sheet']} · "
        f"metrics {t['with_render_metrics']}"
    )
    for v in ("pass", "hold", "rework", "fail", "pending"):
        n = t[f"verdict_{v}"]
        if n:
            console.print(f"  {v}: {n}")

    if check and t["verdict_pending"]:
        pending = [e["slug"] for e in record["entries"] if e["verdict"] == "pending"]
        console.print(f"[red]pending verdicts:[/red] {', '.join(pending)}")
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
