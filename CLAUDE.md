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
```

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

## Environment Variables
See `.env.example`. Key vars: `ANTHROPIC_API_KEY`, `YOUTUBE_CLIENT_SECRET`, `BLENDER_PATH`
