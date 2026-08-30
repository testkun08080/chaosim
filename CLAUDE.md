# Chaosim — Chaos Simulation Video Automation

## Project Overview
Automated pipeline: concept → footage → render → YouTube Shorts upload.

A concept's `source:` decides how the footage is made. All three end at the same
two files (`outputs/renders/<slug>.mp4` + `<slug>_events.json`), which is why
nothing after the render stage branches on it:

| `source:` | footage | SFX timing |
|---|---|---|
| `blender` (default) | physics simulation | from the bake — exact |
| `comfyui` | generated from prompts | cue sheet, snapped to measured onsets |
| `hybrid` | Blender sim + ComfyUI look assets | from the bake — exact |

See `docs/comfyui-pipeline.md` for setup, costs and how to write a cut list.

## Key Commands
```bash
# Generate new concept with AI
python scripts/chaosim.py plan --topic "double pendulum"

# Run simulation + render
python scripts/chaosim.py render concepts/sample_001_double_pendulum.yaml

# Full pipeline
python scripts/chaosim.py run concepts/sample_001_double_pendulum.yaml

# Upload to YouTube
python scripts/chaosim.py upload outputs/renders/double_pendulum_001.mp4

# Cross-check every concept against its scene script (no render, seconds)
python scripts/chaosim.py catalog          # docs/catalog/README.md + outputs/catalog/*.{json,csv}
python scripts/chaosim.py catalog --check  # exit 1 on any error-level finding

# Phase 1 judging data (render metrics + verdicts) -> outputs/gate1/*.{json,csv}
python scripts/chaosim.py gate1-report

# Generate + cache the sound effects a concept's events call for (render first)
python scripts/chaosim.py sfx-build concepts/comfyui/<slug>.yaml --dry-run  # price it
python scripts/chaosim.py sfx-build concepts/comfyui/<slug>.yaml

# Does the sound land on the picture? -> docs/sfx/README.md + outputs/sfx/*
python scripts/chaosim.py sfx-report

# Price a ComfyUI render before sending anything (video is ~$0.25/shot)
python scripts/chaosim.py render concepts/comfyui/<slug>.yaml --dry-run
```

## Cost
`source: comfyui` spends real money per shot. Never run one without `--dry-run`
first. `CHAOSIM_COMFY_DRY_RUN=1` turns every ComfyUI call into a dry run.
`compose` does not generate sound effects by default — `sfx-build` is the one
place that spends on audio.

## Concept/Scene Health
`docs/catalog/README.md` is generated — never edit it. It reports which concepts point at a
scene script that does not exist, and which `params:` keys never reach the code.
That last one matters: `runner.py` calls `run_simulation()` with **no arguments**, so any
scene that uses physics constants outside `setup_scene(params)` silently ignores its YAML.
Check the catalog before tuning params — otherwise the edit does nothing.

For `source: comfyui` it checks the equivalents on that side: an unregistered
recipe, `comfyui:` keys no recipe reads, a `duration` the model will refuse, a
cue past the end of its shot, and `no-cues` — which renders a perfectly good
video with no sound at all.

Human-readable views live in `docs/`; machine-readable data goes to `outputs/` (gitignored,
so CI surfaces it as the `catalog-report` / `gate1-report` artifacts). The one judging
artefact that IS committed is `docs/gate1/verdicts.yaml` — the pass/rework/fail record.
Numbers can always be regenerated; the reason a concept was rejected cannot.

## Production Workflow (phased)
Videos are produced through gated phases — see `docs/production-plan.md`:
concept → **vertical slice** (low-res few-frame camera/material test, must pass the gate before
any `medium`/`high`/`ultra` render) → variation expansion → composite → finish/upload.
SFX design and the compositing sound proposal live in `docs/sfx-design.md`;
`docs/sfx/README.md` is the generated measurement of whether the sound actually lands.

## Architecture
- `pipeline/` — orchestration logic (planner, renderer, uploader)
- `simulators/blender/scenes/` — one Python file per simulation type, runs inside Blender
- `simulators/comfyui/recipes/` — one Python file per ComfyUI recipe. Unlike scene
  scripts these run in *this* interpreter, so they may import from `pipeline/`
- `concepts/` — YAML concept files (input to pipeline)
- `concepts/comfyui/` — the `source: comfyui` / `hybrid` versions
- `config/` — settings and render presets

## Sound
Events name a *role*, never a file. `assets/audio/catalog.yaml` resolves a role
three ways, in order: a file under `assets/audio/sfx/<role>/`, a ComfyUI
generation cached by prompt hash, then a macOS system sound as a last resort.
An event's `intensity` picks the variant and sets the volume; near-simultaneous
events are thinned and each hit is detuned slightly, so a chain of impacts does
not read as one sample on a timer. `docs/sfx-design.md` explains why each of
those matters.

## Adding a New Simulator
1. Create `simulators/blender/scenes/my_sim.py` implementing `setup_scene(params)` and `run_simulation()`
2. Add concept YAML to `concepts/`
3. Register in `simulators/blender/__init__.py`

## Adding a New ComfyUI Recipe
1. Create `simulators/comfyui/recipes/my_recipe.py` implementing `build_jobs(concept, params, settings)`
   (plus `apply_assets(concept, produced)` if it backs a `source: hybrid` concept)
2. Register in `simulators/comfyui/__init__.py`
3. Workflow JSON lives in the **comfyui-sandbox** repo, not here. Add its node-id
   mapping to `WORKFLOW_INPUTS` in `simulators/comfyui/__init__.py` — one table,
   so a renumbered workflow is a one-line fix rather than a hunt.

## Blender Scripts
All scene scripts run via: `blender --background --python simulators/blender/runner.py -- <concept.yaml>`
Scripts must be self-contained (no relative imports) as they run inside Blender's Python.

## HyperFrames Composition Layer
HTML templates in `templates/hyperframes/` and `templates/thumbnail/` render via HyperFrames CLI
(or ffmpeg stub fallback). Templates follow the standalone-composition contract:
- Root `<div data-composition-id="main" data-duration="N">` in `<body>`
- Exactly one paused GSAP timeline registered at `window.__timelines["main"]`
- Animations defined in `{% block timeline %}` with `tl.from(selector, ...)` tweens

GSAP is loaded from `.agents/skills/graphic-overlays/assets/vendor/gsap.min.js` if available,
otherwise from CDN. HyperFrames `render` and `snapshot` commands are driven as subprocesses,
similar to Blender.

If you see `data-composition-id not registered` or 45-second timeouts during HyperFrames render:
1. Ensure the timeline is registered at `window.__timelines["main"]` (not a sub-object)
2. Check `.env.example` for `HYPERFRAMES_FFMPEG_PATH` if static-ffmpeg v8 incompatibilities arise

## Environment Variables
See `.env.example`. Key vars: `ANTHROPIC_API_KEY`, `YOUTUBE_CLIENT_SECRET_PATH`, `BLENDER_PATH`,
`HYPERFRAMES_PATH`, `HYPERFRAMES_FFMPEG_PATH` (if needed), `VOICEVOX_URL`,
`COMFYUI_SANDBOX_PATH`.

`COMFY_API_KEY` is **not** set here. It lives in the comfyui-sandbox checkout's
own `.env`, which is the only place that talks to the API — one place for the key.

YouTube upload has two credential paths. Locally it uses `YOUTUBE_CLIENT_SECRET_PATH` plus a
pickled token cache; on GitHub Actions it uses `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` /
`YOUTUBE_REFRESH_TOKEN`, which take priority. Mint those three with
`python scripts/chaosim.py youtube-auth` — see `docs/ci.md`.
