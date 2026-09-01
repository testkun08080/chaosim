"""Static health check across concepts and the code they claim to drive.

Answers the question the pipeline could not answer before a render: *does this
concept actually drive the code it claims to drive?* Nothing here imports
Blender or renders anything — scene scripts ``import bpy`` at module scope, so
they are read with :mod:`ast` rather than imported. ComfyUI recipes are read the
same way for symmetry, and so a syntax error in one is a finding rather than a
crash.

A concept is checked against the backend it declares (``source``). A
``comfyui`` concept has no scene script and no ``params``; what it has instead
is a cut list and a cue sheet, and those have their own ways of being silently
wrong — a duration the model will refuse, a cue past the end of its shot, or no
cues at all, which renders a video that is simply mute.

The split is deliberate: everything above ``build_catalog`` is pure (dicts in,
dicts out) so it is unit-testable, and only the CLI layer touches the
filesystem for output.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# The contract runner.py feature-detects with hasattr(). Keep in sync with
# simulators/blender/runner.py.
SCENE_HOOKS = ("setup_scene", "run_simulation", "render_staged", "collect_impact_events")

# The contract pipeline/comfyui_render.py calls. ``apply_assets`` is what makes
# a recipe usable by a hybrid concept.
RECIPE_HOOKS = ("build_jobs", "apply_assets")

REQUIRED_FIELDS = ("title", "slug", "duration_sec")
# Only a backend that runs a Blender scene needs to name one.
BLENDER_REQUIRED_FIELDS = ("scene_script",)
KNOWN_PRESETS = ("preview", "medium", "high", "ultra")
KNOWN_SOURCES = ("blender", "comfyui", "hybrid")

# Mirrors simulators/comfyui/recipes/generative_shots.py and pipeline/sfx_events.py.
ALLOWED_SHOT_DURATIONS = (5, 10, 15)
KNOWN_CUE_TYPES = ("impact", "drop", "collapse", "whoosh", "settle", "tick")

# sim.yml derives artifact names from the slug, so the same charset applies.
SLUG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _get_keys(tree: ast.AST, holders: tuple[str, ...]) -> set[str]:
    """Collect literal keys from ``<holder>.get("name")`` calls."""
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "get"):
            continue
        if not (isinstance(fn.value, ast.Name) and fn.value.id in holders):
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            keys.add(node.args[0].value)
    return keys


def _param_keys(tree: ast.AST) -> set[str]:
    """Collect literal keys from ``params.get("name")`` calls."""
    return _get_keys(tree, ("params",))


def scan_scene(path: Path) -> dict:
    """Read one scene script's contract and the params it consumes."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    top_level = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return {
        "name": path.stem,
        "hooks": {h: h in top_level for h in SCENE_HOOKS},
        "params": _param_keys(tree),
        "staged": "render_staged" in top_level,
        "emits_events": "collect_impact_events" in top_level,
    }


def scan_scenes(scenes_dir: Path) -> dict[str, dict]:
    """Scan every registered scene script. Leading-underscore files are templates."""
    out = {}
    for p in sorted(scenes_dir.glob("*.py")):
        if p.stem.startswith("_"):
            continue
        out[p.stem] = scan_scene(p)
    return out


def scan_recipe(path: Path) -> dict:
    """Read one ComfyUI recipe's contract and the concept keys it consumes.

    A recipe reads the concept's ``comfyui`` block through a handful of local
    names (``cfg`` for the block, ``raw`` for one shot or asset), so every
    ``.get("literal")` on those is treated as a key the recipe understands.
    Over-approximating is the right way round here: the check it feeds is a
    warning about config that never reaches code, and a false "this is dead"
    would be worse than a missed one.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    top_level = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return {
        "name": path.stem,
        "hooks": {h: h in top_level for h in RECIPE_HOOKS},
        "keys": _get_keys(tree, ("cfg", "raw", "shot", "asset", "concept", "params")),
        "asset_recipe": "apply_assets" in top_level,
    }


def scan_recipes(recipes_dir: Path) -> dict[str, dict]:
    """Scan every ComfyUI recipe. Leading-underscore files are not recipes."""
    out = {}
    if not recipes_dir.is_dir():
        return out
    for p in sorted(recipes_dir.glob("*.py")):
        if p.stem.startswith("_"):
            continue
        out[p.stem] = scan_recipe(p)
    return out


def _validate_comfyui(concept: dict, recipes: dict[str, dict], source: str) -> list[dict]:
    """Findings specific to the ComfyUI side of a concept."""
    findings: list[dict] = []
    cfg = concept.get("comfyui") or {}

    if not cfg:
        findings.append({"level": "error", "code": "missing-comfyui",
                         "message": f"source: {source} なのに `comfyui:` ブロックが無い"})
        return findings

    recipe_name = str(cfg.get("recipe") or "generative_shots")
    recipe = recipes.get(recipe_name)
    if recipe is None:
        findings.append({"level": "error", "code": "missing-recipe",
                         "message": f"recipe `{recipe_name}.py` が "
                                    f"simulators/comfyui/recipes/ に存在しない"})
        return findings

    if source == "hybrid" and not recipe["asset_recipe"]:
        findings.append({"level": "error", "code": "not-an-asset-recipe",
                         "message": f"source: hybrid は素材を作る recipe が要るが "
                                    f"`{recipe_name}` に apply_assets が無い"})
    if source == "comfyui" and recipe["asset_recipe"]:
        findings.append({"level": "warn", "code": "asset-recipe-as-footage",
                         "message": f"`{recipe_name}` は素材用の recipe。"
                                    f"source: comfyui では映像が作られない可能性が高い"})

    declared = {k for k in cfg if k != "recipe"}
    dead = sorted(declared - recipe["keys"])
    if dead:
        findings.append({
            "level": "warn", "code": "dead-comfyui-keys",
            "message": f"{len(dead)}/{len(declared)} の `comfyui:` の項目が "
                       f"`{recipe_name}` に届いていない: " + ", ".join(f"`{d}`" for d in dead),
        })

    shots = cfg.get("shots") or []
    assets = cfg.get("assets") or []
    if source == "comfyui" and not shots:
        findings.append({"level": "error", "code": "no-shots",
                         "message": "source: comfyui なのに `comfyui.shots` が空"})
    if source == "hybrid" and not assets:
        findings.append({"level": "error", "code": "no-assets",
                         "message": "source: hybrid なのに `comfyui.assets` が空"})

    total_cues = 0
    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            continue
        name = shot.get("name") or f"shot_{index:02d}"
        duration = shot.get("duration")
        if duration is not None and duration not in ALLOWED_SHOT_DURATIONS:
            findings.append({
                "level": "warn", "code": "bad-shot-duration",
                "message": f"`{name}` の duration {duration} はモデルが受け取らない値。"
                           f"{'/'.join(str(d) for d in ALLOWED_SHOT_DURATIONS)} 秒に丸められる",
            })
        if not str(shot.get("prompt") or "").strip():
            findings.append({"level": "error", "code": "empty-shot-prompt",
                             "message": f"`{name}` に prompt（動きの指示）が無い"})
        for cue in shot.get("cues") or []:
            if not isinstance(cue, dict):
                continue
            total_cues += 1
            cue_type = cue.get("type")
            if cue_type is not None and cue_type not in KNOWN_CUE_TYPES:
                findings.append({
                    "level": "warn", "code": "bad-cue-type",
                    "message": f"`{name}` の cue type `{cue_type}` は未知。"
                               f"impact 扱いになる（{'/'.join(KNOWN_CUE_TYPES)}）",
                })
            try:
                t = float(cue.get("t", 0.0))
            except (TypeError, ValueError):
                continue
            if duration and t > float(duration):
                findings.append({
                    "level": "warn", "code": "cue-out-of-shot",
                    "message": f"`{name}` の cue t={t} がショート尺 {duration}s を超えている。"
                               f"次のショットに音が乗らないよう捨てられる",
                })

    if source == "comfyui" and shots and not total_cues:
        findings.append({"level": "warn", "code": "no-cues",
                         "message": "cue が1つも無い。生成映像にはベイクが無いので、"
                                    "このままだと効果音が一切鳴らない"})
    return findings


def scan_runner_params(runner_path: Path) -> set[str]:
    """Params consumed by runner.py itself rather than by a scene script.

    ``face_counts`` and ``stage_duration_sec`` are read here, so a concept that
    declares them is not declaring dead config even though no scene reads them
    through ``params.get``.
    """
    return _param_keys(ast.parse(runner_path.read_text(encoding="utf-8")))


def validate_concept(concept: dict, scenes: dict[str, dict], runner_params: set[str],
                     recipes: dict[str, dict] | None = None) -> list[dict]:
    """Return findings for one concept, most severe first.

    A concept carrying ``status: blocked`` is a known-incomplete placeholder, so
    its missing scene script is reported as a warning rather than an error —
    otherwise every CI run would be red on work that is deliberately parked.
    """
    findings: list[dict] = []
    recipes = recipes or {}
    blocked = str(concept.get("status", "")).strip().lower() == "blocked"

    source = str(concept.get("source") or "blender").lower()
    if source not in KNOWN_SOURCES:
        findings.append({"level": "error", "code": "bad-source",
                         "message": f"source `{source}` は未知（{'/'.join(KNOWN_SOURCES)}）"})
        source = "blender"

    required = REQUIRED_FIELDS
    if source != "comfyui":
        required = required + BLENDER_REQUIRED_FIELDS
    for field in required:
        if not concept.get(field):
            findings.append({"level": "error", "code": "missing-field",
                             "message": f"必須フィールド `{field}` が無い"})

    if source == "blender" and concept.get("comfyui"):
        findings.append({"level": "warn", "code": "unused-comfyui",
                         "message": "`comfyui:` ブロックがあるが source が blender なので使われない"})
    if source != "blender":
        findings += _validate_comfyui(concept, recipes, source)
    if source == "comfyui" and concept.get("scene_script"):
        findings.append({"level": "warn", "code": "unused-scene-script",
                         "message": "source: comfyui では scene_script は使われない"})

    slug = str(concept.get("slug") or "")
    if slug and not SLUG_RE.fullmatch(slug):
        findings.append({"level": "error", "code": "bad-slug",
                         "message": f"slug `{slug}` が artifact 名に使えない文字を含む"})

    scene_name = "" if source == "comfyui" else str(concept.get("scene_script") or "")
    scene = scenes.get(scene_name)
    if scene_name and scene is None:
        findings.append({"level": "warn" if blocked else "error", "code": "missing-scene",
                         "message": f"scene_script `{scene_name}.py` が存在しない"
                                    + ("（status: blocked のため警告どまり）" if blocked else "")})

    preset = concept.get("render_preset")
    if preset and preset not in KNOWN_PRESETS:
        findings.append({"level": "error", "code": "bad-preset",
                         "message": f"render_preset `{preset}` は未知（{'/'.join(KNOWN_PRESETS)}）"})

    if blocked:
        findings.append({"level": "warn", "code": "blocked",
                         "message": "status: blocked — レンダー対象外"})

    if scene is not None:
        declared = set((concept.get("params") or {}).keys())
        reachable = scene["params"] | runner_params
        dead = sorted(declared - reachable)
        if dead:
            findings.append({
                "level": "warn", "code": "dead-params",
                "message": f"{len(dead)}/{len(declared)} の params がコードに届いていない: "
                           + ", ".join(f"`{d}`" for d in dead),
            })
        if not scene["hooks"]["setup_scene"] and not scene["staged"]:
            findings.append({"level": "error", "code": "no-entrypoint",
                             "message": f"`{scene_name}.py` に setup_scene も render_staged も無い"})

    order = {"error": 0, "warn": 1}
    findings.sort(key=lambda f: order.get(f["level"], 9))
    return findings


def build_catalog(concepts: list[tuple[str, dict]], scenes: dict[str, dict],
                  runner_params: set[str], gate1_slugs: frozenset[str] = frozenset(),
                  recipes: dict[str, dict] | None = None) -> dict:
    """Assemble the full view context. ``concepts`` is [(repo-relative path, dict)]."""
    recipes = recipes or {}
    entries = []
    scene_usage: dict[str, list[str]] = {name: [] for name in scenes}
    recipe_usage: dict[str, list[str]] = {name: [] for name in recipes}

    for rel_path, concept in concepts:
        slug = str(concept.get("slug") or Path(rel_path).stem)
        source = str(concept.get("source") or "blender").lower()
        scene_name = "" if source == "comfyui" else str(concept.get("scene_script") or "")
        findings = validate_concept(concept, scenes, runner_params, recipes)
        if scene_name in scene_usage:
            scene_usage[scene_name].append(slug)

        recipe_name = ""
        if source != "blender":
            recipe_name = str((concept.get("comfyui") or {}).get("recipe") or "generative_shots")
            if recipe_name in recipe_usage:
                recipe_usage[recipe_name].append(slug)

        declared = set((concept.get("params") or {}).keys())
        scene = scenes.get(scene_name)
        reachable = (scene["params"] | runner_params) if scene else set()
        shots = (concept.get("comfyui") or {}).get("shots") or []
        cue_count = sum(len(s.get("cues") or []) for s in shots if isinstance(s, dict))

        entries.append({
            "slug": slug,
            "path": rel_path,
            "title": concept.get("title") or slug,
            "hook": concept.get("hook") or "",
            "source": source,
            "recipe": recipe_name,
            "shots": len(shots),
            "cues": cue_count,
            "scene": scene_name,
            "duration_sec": concept.get("duration_sec"),
            "preset": concept.get("render_preset") or "",
            "staged": bool(scene and scene["staged"]),
            "params_declared": len(declared),
            "params_live": len(declared & reachable) if scene else 0,
            "findings": findings,
            "errors": sum(1 for f in findings if f["level"] == "error"),
            "warnings": sum(1 for f in findings if f["level"] == "warn"),
            "has_gate1": slug in gate1_slugs,
        })

    entries.sort(key=lambda e: (-e["errors"], -e["warnings"], e["slug"]))

    # Only concepts whose scene script resolves can have their params checked.
    # Counting a blocked concept's params as "dead" would overstate the gap —
    # they are unverifiable, not proven unreachable.
    checkable = [e for e in entries if e["scene"] in scenes]
    total_declared = sum(e["params_declared"] for e in checkable)
    total_live = sum(e["params_live"] for e in checkable)
    unverifiable = sum(e["params_declared"] for e in entries if e["scene"] not in scenes)

    scene_rows = []
    for name, info in sorted(scenes.items()):
        scene_rows.append({
            "name": name,
            "hooks": info["hooks"],
            "param_count": len(info["params"]),
            "used_by": sorted(scene_usage.get(name, [])),
        })

    recipe_rows = [
        {
            "name": name,
            "hooks": info["hooks"],
            "asset_recipe": info["asset_recipe"],
            "key_count": len(info["keys"]),
            "used_by": sorted(recipe_usage.get(name, [])),
        }
        for name, info in sorted(recipes.items())
    ]

    return {
        "entries": entries,
        "scenes": scene_rows,
        "recipes": recipe_rows,
        "runner_params": sorted(runner_params),
        "totals": {
            "concepts": len(entries),
            "by_source": {
                src: sum(1 for e in entries if e["source"] == src) for src in KNOWN_SOURCES
            },
            "errors": sum(e["errors"] for e in entries),
            "warnings": sum(e["warnings"] for e in entries),
            "params_declared": total_declared,
            "params_live": total_live,
            "params_dead": total_declared - total_live,
            "params_unverifiable": unverifiable,
            "params_live_pct": round(total_live * 100 / total_declared) if total_declared else 100,
        },
    }


CSV_FIELDS = [
    "slug", "title", "source", "scene_script", "recipe", "shots", "cues",
    "duration_sec", "preset", "staged",
    "params_declared", "params_live", "params_dead",
    "errors", "warnings", "finding_codes", "has_gate1", "path",
]


def catalog_csv_rows(ctx: dict) -> list[dict]:
    """Flatten the catalog context to one row per concept for spreadsheet review."""
    rows = []
    for e in ctx["entries"]:
        rows.append({
            "slug": e["slug"],
            "title": e["title"],
            "source": e["source"],
            "scene_script": e["scene"],
            "recipe": e["recipe"],
            "shots": e["shots"],
            "cues": e["cues"],
            "duration_sec": e["duration_sec"],
            "preset": e["preset"],
            "staged": int(e["staged"]),
            "params_declared": e["params_declared"],
            "params_live": e["params_live"],
            "params_dead": e["params_declared"] - e["params_live"],
            "errors": e["errors"],
            "warnings": e["warnings"],
            # Space-separated so the cell stays one field without quoting games.
            "finding_codes": " ".join(f["code"] for f in e["findings"]),
            "has_gate1": int(e["has_gate1"]),
            "path": e["path"],
        })
    return rows


def collect_catalog(repo_root: Path = REPO_ROOT) -> dict:
    """Read the repo and build the catalog context."""
    from pipeline.planner import load_concept

    scenes = scan_scenes(repo_root / "simulators/blender/scenes")
    recipes = scan_recipes(repo_root / "simulators/comfyui/recipes")
    runner_params = scan_runner_params(repo_root / "simulators/blender/runner.py")

    concepts = []
    for p in sorted((repo_root / "concepts").rglob("*.yaml")):
        concept = load_concept(p) or {}
        concepts.append((p.relative_to(repo_root).as_posix(), concept))

    gate1 = repo_root / "docs/gate1"
    gate1_slugs = frozenset(
        p.name[: -len("_contact.png")] for p in gate1.glob("*_contact.png")
    ) if gate1.is_dir() else frozenset()

    return build_catalog(concepts, scenes, runner_params, gate1_slugs, recipes)
