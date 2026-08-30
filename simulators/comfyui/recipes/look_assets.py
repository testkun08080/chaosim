"""Hybrid material: ComfyUI makes the look, Blender still does the physics.

For a concept whose simulation is sound but whose picture is not, replacing the
whole render with generated footage throws away the one thing that works — the
bake, and with it the exact impact times the sound depends on. This recipe
generates only *assets* (a backplate, an environment image, a texture), writes
them under ``assets/generated/<slug>/``, and points concept params at the files.
The Blender path then runs unchanged.

Each entry names the params key it fills, so the scene needs no knowledge of
where the file came from::

    comfyui:
      recipe: look_assets
      assets:
        - param: backdrop_image
          prompt: "..."
          size: "1344x768"
"""

from __future__ import annotations

from pathlib import Path

GENERATED_ROOT = Path("assets/generated")

DEFAULT_SIZE = "1344x768"           # wide: an environment image wraps horizontally
DEFAULT_NEGATIVE = "text, watermark, logo, people, hands, ui, caption, border"


def plan_assets(concept: dict) -> list[dict]:
    """Normalise ``concept["comfyui"]["assets"]`` into the assets we generate."""
    cfg = concept.get("comfyui") or {}
    slug = concept.get("slug", "render")
    base_seed = int(cfg.get("seed") or 0)

    assets: list[dict] = []
    for index, raw in enumerate(cfg.get("assets") or [], start=1):
        param = str(raw.get("param") or "")
        if not param:
            continue
        name = str(raw.get("name") or param)
        assets.append({
            "param": param,
            "name": name,
            "prompt": str(raw.get("prompt") or ""),
            "negative_prompt": str(raw.get("negative_prompt") or DEFAULT_NEGATIVE),
            "size": str(raw.get("size") or cfg.get("asset_size") or DEFAULT_SIZE),
            "seed": int(raw.get("seed") if raw.get("seed") is not None else base_seed + index),
            "path": GENERATED_ROOT / slug / f"{name}.png",
        })
    return assets


def build_jobs(concept: dict, params: dict | None = None) -> list[dict]:
    """One image-generation job per declared asset."""
    slug = concept.get("slug", "render")
    return [
        {
            "workflow": "01_image/recraft_v4_text_to_image.json",
            "inputs": {
                "prompt": asset["prompt"],
                "negative_prompt": asset["negative_prompt"],
                "size": asset["size"],
                "seed": asset["seed"],
                "prefix": f"{slug}/{asset['name']}",
            },
            "name": asset["name"],
            "param": asset["param"],
            "path": asset["path"],
        }
        for asset in plan_assets(concept)
    ]


def apply_assets(concept: dict, produced: dict[str, Path]) -> dict:
    """Return a copy of ``concept`` with ``params`` pointing at the generated files.

    Only params whose file actually exists are set: a job that was skipped (a
    dry run, or a stub with no ffmpeg) must leave the concept's own value in
    place rather than pointing the scene at nothing.
    """
    patched = dict(concept)
    params = dict(patched.get("params") or {})
    for asset in plan_assets(concept):
        path = produced.get(asset["param"])
        if path and Path(path).is_file():
            params[asset["param"]] = str(path)
    patched["params"] = params
    return patched
