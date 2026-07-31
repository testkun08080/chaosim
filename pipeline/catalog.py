"""Static health check across concepts and Blender scene scripts.

Answers the question the pipeline could not answer before a render: *does this
concept actually drive the code it claims to drive?* Nothing here imports
Blender or renders anything — scene scripts ``import bpy`` at module scope, so
they are read with :mod:`ast` rather than imported.

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

REQUIRED_FIELDS = ("title", "slug", "scene_script", "duration_sec")
KNOWN_PRESETS = ("preview", "medium", "high", "ultra")

# sim.yml derives artifact names from the slug, so the same charset applies.
SLUG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _param_keys(tree: ast.AST) -> set[str]:
    """Collect literal keys from ``params.get("name")`` calls."""
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "get"):
            continue
        if not (isinstance(fn.value, ast.Name) and fn.value.id == "params"):
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            keys.add(node.args[0].value)
    return keys


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


def scan_runner_params(runner_path: Path) -> set[str]:
    """Params consumed by runner.py itself rather than by a scene script.

    ``face_counts`` and ``stage_duration_sec`` are read here, so a concept that
    declares them is not declaring dead config even though no scene reads them
    through ``params.get``.
    """
    return _param_keys(ast.parse(runner_path.read_text(encoding="utf-8")))


def validate_concept(concept: dict, scenes: dict[str, dict], runner_params: set[str]) -> list[dict]:
    """Return findings for one concept, most severe first.

    A concept carrying ``status: blocked`` is a known-incomplete placeholder, so
    its missing scene script is reported as a warning rather than an error —
    otherwise every CI run would be red on work that is deliberately parked.
    """
    findings: list[dict] = []
    blocked = str(concept.get("status", "")).strip().lower() == "blocked"

    for field in REQUIRED_FIELDS:
        if not concept.get(field):
            findings.append({"level": "error", "code": "missing-field",
                             "message": f"必須フィールド `{field}` が無い"})

    slug = str(concept.get("slug") or "")
    if slug and not SLUG_RE.fullmatch(slug):
        findings.append({"level": "error", "code": "bad-slug",
                         "message": f"slug `{slug}` が artifact 名に使えない文字を含む"})

    scene_name = str(concept.get("scene_script") or "")
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
                  runner_params: set[str], gate1_slugs: frozenset[str] = frozenset()) -> dict:
    """Assemble the full view context. ``concepts`` is [(repo-relative path, dict)]."""
    entries = []
    scene_usage: dict[str, list[str]] = {name: [] for name in scenes}

    for rel_path, concept in concepts:
        slug = str(concept.get("slug") or Path(rel_path).stem)
        scene_name = str(concept.get("scene_script") or "")
        findings = validate_concept(concept, scenes, runner_params)
        if scene_name in scene_usage:
            scene_usage[scene_name].append(slug)

        declared = set((concept.get("params") or {}).keys())
        scene = scenes.get(scene_name)
        reachable = (scene["params"] | runner_params) if scene else set()

        entries.append({
            "slug": slug,
            "path": rel_path,
            "title": concept.get("title") or slug,
            "hook": concept.get("hook") or "",
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

    return {
        "entries": entries,
        "scenes": scene_rows,
        "runner_params": sorted(runner_params),
        "totals": {
            "concepts": len(entries),
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
    "slug", "title", "scene_script", "duration_sec", "preset", "staged",
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
            "scene_script": e["scene"],
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
    runner_params = scan_runner_params(repo_root / "simulators/blender/runner.py")

    concepts = []
    for p in sorted((repo_root / "concepts").rglob("*.yaml")):
        concept = load_concept(p) or {}
        concepts.append((p.relative_to(repo_root).as_posix(), concept))

    gate1 = repo_root / "docs/gate1"
    gate1_slugs = frozenset(
        p.name[: -len("_contact.png")] for p in gate1.glob("*_contact.png")
    ) if gate1.is_dir() else frozenset()

    return build_catalog(concepts, scenes, runner_params, gate1_slugs)
