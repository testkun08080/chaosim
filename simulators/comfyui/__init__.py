"""ComfyUI-backed material generation.

The counterpart to ``simulators/blender/``. A *recipe* plays the role a scene
script plays for Blender: it turns a concept into work for the renderer. The
difference is where the code runs — Blender scenes execute inside Blender's own
interpreter and must be self-contained, whereas recipes run in this pipeline's
interpreter and may import from ``pipeline``.

Register new recipes here, the same way scenes are registered in
``simulators/blender/__init__.py``.
"""

AVAILABLE_RECIPES = [
    "generative_shots",
    "look_assets",
]

# Logical input name -> "<node id>.<input name>" in the sandbox workflow.
#
# comfy_run.py addresses inputs by node id, so these numbers are a contract with
# comfyui-sandbox. Keeping them in one table means a renumbered workflow is a
# one-line fix here rather than a hunt through the recipes.
WORKFLOW_INPUTS: dict[str, dict[str, str]] = {
    "08_video/keyframe_then_video.json": {
        "keyframe_prompt": "1.prompt",
        "keyframe_negative": "1.negative_prompt",
        "keyframe_size": "1.model.size",
        "keyframe_seed": "1.seed",
        "keyframe_prefix": "2.filename_prefix",
        "prompt": "10.prompt",
        "negative_prompt": "10.negative_prompt",
        "resolution": "10.resolution",
        "duration": "10.duration",
        "seed": "10.seed",
        "generate_audio": "10.generate_audio",
        "prefix": "20.filename_prefix",
    },
    "08_video/wan_image_to_video.json": {
        "image": "1.image",
        "prompt": "10.prompt",
        "negative_prompt": "10.negative_prompt",
        "resolution": "10.resolution",
        "duration": "10.duration",
        "seed": "10.seed",
        "generate_audio": "10.generate_audio",
        "prefix": "20.filename_prefix",
    },
    "08_video/video_with_audio.json": {
        "image": "1.image",
        "prompt": "10.prompt",
        "negative_prompt": "10.negative_prompt",
        "resolution": "10.resolution",
        "duration": "10.duration",
        "seed": "10.seed",
        "prefix": "20.filename_prefix",
        "audio_prefix": "40.filename_prefix",
    },
    "01_image/recraft_v4_text_to_image.json": {
        "prompt": "12.prompt",
        "negative_prompt": "12.negative_prompt",
        "size": "12.model.size",
        "seed": "12.seed",
        "prefix": "5.filename_prefix",
    },
    "07_sfx/elevenlabs_text_to_sound_effects.json": {
        "prompt": "136.text",
        "duration": "136.model.duration",
        "loop": "136.model.loop",
        "prompt_influence": "136.model.prompt_influence",
        "prefix": "137.filename_prefix",
    },
    "07_sfx/sonilo_text_to_music.json": {
        "prompt": "726.prompt",
        "duration": "726.duration",
        "seed": "726.seed",
        "prefix": "728.filename_prefix",
    },
}


def resolve_overrides(workflow: str, values: dict) -> dict[str, object]:
    """Map logical input names to the ``<node>.<input>`` keys comfy_run expects.

    Raises on an unknown name rather than silently dropping it — a typo that
    quietly leaves a prompt at its template default is expensive to notice,
    because the render succeeds and only looks wrong.
    """
    table = WORKFLOW_INPUTS.get(workflow)
    if table is None:
        raise KeyError(
            f"no input mapping for workflow {workflow!r} "
            f"(known: {', '.join(sorted(WORKFLOW_INPUTS))})"
        )
    out: dict[str, object] = {}
    for name, value in values.items():
        if value is None:
            continue
        if name not in table:
            raise KeyError(
                f"{workflow}: unknown input {name!r} (known: {', '.join(sorted(table))})"
            )
        out[table[name]] = value
    return out
