# Chaosim — Chaos Simulation Video Automation

## Project Overview
Automated pipeline: concept → Blender simulation → render → YouTube Shorts upload.

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
python scripts/chaosim.py catalog          # regenerates docs/catalog/README.md
python scripts/chaosim.py catalog --check  # exit 1 on any error-level finding
```

## Concept/Scene Health
`docs/catalog/README.md` is generated — never edit it. It reports which concepts point at a
scene script that does not exist, and which `params:` keys never reach the code.
That last one matters: `runner.py` calls `run_simulation()` with **no arguments**, so any
scene that uses physics constants outside `setup_scene(params)` silently ignores its YAML.
Check the catalog before tuning params — otherwise the edit does nothing.

## Production Workflow (phased)
Videos are produced through gated phases — see `docs/production-plan.md`:
concept → **vertical slice** (low-res few-frame camera/material test, must pass the gate before
any `medium`/`high`/`ultra` render) → variation expansion → composite → finish/upload.
SFX design and the compositing sound proposal live in `docs/sfx-design.md`.

## Architecture
- `pipeline/` — orchestration logic (planner, renderer, uploader)
- `simulators/blender/scenes/` — one Python file per simulation type, runs inside Blender
- `concepts/` — YAML concept files (input to pipeline)
- `config/` — settings and render presets

## Adding a New Simulator
1. Create `simulators/blender/scenes/my_sim.py` implementing `setup_scene(params)` and `run_simulation()`
2. Add concept YAML to `concepts/`
3. Register in `simulators/blender/__init__.py`

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
See `.env.example`. Key vars: `ANTHROPIC_API_KEY`, `YOUTUBE_CLIENT_SECRET`, `BLENDER_PATH`,
`HYPERFRAMES_PATH`, `HYPERFRAMES_FFMPEG_PATH` (if needed), `VOICEVOX_URL`
