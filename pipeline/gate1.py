"""Phase 1 (vertical slice) judging data.

Turns what `gate-review` collected into `docs/gate1/` — contact sheets, trimmed
render logs, SFX event sidecars — into a machine-readable record, and merges it
with the human verdicts in ``docs/gate1/verdicts.yaml``.

The render numbers are measured; the verdict is not. Keeping them in one record
is the point: a "fail" is only meaningful next to the frame count and resolution
it was judged at, because the CI slice is shorter than the concept's real
duration.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# The five Gate 1->2 checks from docs/production-plan.md, in order.
GATE_KEYS = ("framing", "look", "sim", "hook", "duration")

VERDICTS = ("pass", "hold", "rework", "fail", "pending")

# runner.py sets resolution_x/y before applying the preset percentage.
BASE_W, BASE_H = 1080, 1920

_ENGINE_RE = re.compile(r"Engine=(\S+) frames=(\d+)-(\d+) res%=(\d+) fps=(\d+)")
_TRUNC_RE = re.compile(r"truncating frame_end (\d+) -> (\d+)")
_STAGE_RE = re.compile(r"stage_duration_sec -> ([\d.]+)s x (\d+) stages")


def parse_render_log(text: str) -> dict:
    """Pull the render facts out of a trimmed `<slug>_render.log`.

    Returns ``{}`` when the sentinel line is absent, which is how a failed or
    stubbed render looks — the caller reports that rather than guessing.
    """
    m = _ENGINE_RE.search(text)
    if not m:
        return {}
    engine, first, last, pct, fps = m.groups()
    first, last, pct, fps = int(first), int(last), int(pct), int(fps)
    frames = last - first + 1

    out = {
        "engine": engine,
        "frames": frames,
        "fps": fps,
        "resolution_pct": pct,
        "width": BASE_W * pct // 100,
        "height": BASE_H * pct // 100,
        "duration_sec": round(frames / fps, 2) if fps else None,
        "full_frames": None,
        "staged": False,
        "stages": None,
        "stage_duration_sec": None,
    }

    trunc = _TRUNC_RE.search(text)
    if trunc:
        # The concept's own length before CHAOSIM_MAX_FRAMES cut it down.
        out["full_frames"] = int(trunc.group(1))

    stage = _STAGE_RE.search(text)
    if stage:
        out["staged"] = True
        out["stage_duration_sec"] = float(stage.group(1))
        out["stages"] = int(stage.group(2))

    return out


def _event_count(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return len(json.loads(path.read_text(encoding="utf-8")).get("events", []))
    except (ValueError, OSError):
        return None


def normalize_verdict(raw: dict | None) -> dict:
    """Coerce one verdicts.yaml entry into a full record.

    An unlisted or malformed slug becomes ``pending`` with all five checks
    unanswered, so a concept never silently looks judged when it is not.
    """
    raw = raw if isinstance(raw, dict) else {}
    verdict = str(raw.get("verdict") or "pending").strip().lower()
    if verdict not in VERDICTS:
        verdict = "pending"

    gate_in = raw.get("gate") if isinstance(raw.get("gate"), dict) else {}
    gate = {}
    for key in GATE_KEYS:
        value = gate_in.get(key)
        gate[key] = value if isinstance(value, bool) else None

    return {
        "verdict": verdict,
        "gate": gate,
        "gate_passed": sum(1 for v in gate.values() if v is True),
        "gate_failed": sum(1 for v in gate.values() if v is False),
        "gate_undecided": sum(1 for v in gate.values() if v is None),
        "note": str(raw.get("note") or "").strip(),
    }


def collect_gate1(gate1_dir: Path, verdicts: dict | None = None) -> dict:
    """Build the Phase 1 record from a collected `docs/gate1/` directory."""
    gate1_dir = Path(gate1_dir)
    verdicts = verdicts or {}

    slugs = sorted(p.name[: -len("_contact.png")]
                   for p in gate1_dir.glob("*_contact.png"))
    # A concept can be judged (or parked) without a contact sheet — keep those
    # visible instead of dropping them.
    slugs = sorted(set(slugs) | {s for s in verdicts if isinstance(s, str)})

    entries = []
    for slug in slugs:
        log = gate1_dir / f"{slug}_render.log"
        contact = gate1_dir / f"{slug}_contact.png"
        metrics = parse_render_log(log.read_text(encoding="utf-8", errors="replace")) if log.exists() else {}

        entry = {
            "slug": slug,
            "contact_sheet": contact.name if contact.exists() else None,
            "contact_bytes": contact.stat().st_size if contact.exists() else None,
            "render": metrics or None,
            "sfx_events": _event_count(gate1_dir / f"{slug}_events.json"),
            **normalize_verdict(verdicts.get(slug)),
        }
        entries.append(entry)

    tally: dict[str, int] = {v: 0 for v in VERDICTS}
    for e in entries:
        tally[e["verdict"]] += 1

    return {
        "gate_keys": list(GATE_KEYS),
        "entries": entries,
        "totals": {
            "concepts": len(entries),
            "with_contact_sheet": sum(1 for e in entries if e["contact_sheet"]),
            "with_render_metrics": sum(1 for e in entries if e["render"]),
            **{f"verdict_{k}": v for k, v in tally.items()},
        },
    }


CSV_FIELDS = [
    "slug", "verdict", "gate_passed", "gate_failed", "gate_undecided",
    *(f"gate_{k}" for k in GATE_KEYS),
    "engine", "width", "height", "fps", "frames", "full_frames", "duration_sec",
    "staged", "stages", "stage_duration_sec", "sfx_events", "contact_sheet", "note",
]


def gate1_csv_rows(record: dict) -> list[dict]:
    """Flatten the Phase 1 record to one row per concept."""
    rows = []
    for e in record["entries"]:
        r = e.get("render") or {}
        row = {
            "slug": e["slug"],
            "verdict": e["verdict"],
            "gate_passed": e["gate_passed"],
            "gate_failed": e["gate_failed"],
            "gate_undecided": e["gate_undecided"],
            "engine": r.get("engine", ""),
            "width": r.get("width", ""),
            "height": r.get("height", ""),
            "fps": r.get("fps", ""),
            "frames": r.get("frames", ""),
            "full_frames": r.get("full_frames") if r.get("full_frames") is not None else "",
            "duration_sec": r.get("duration_sec", ""),
            "staged": int(bool(r.get("staged"))) if r else "",
            "stages": r.get("stages") if r.get("stages") is not None else "",
            "stage_duration_sec": r.get("stage_duration_sec") if r.get("stage_duration_sec") is not None else "",
            "sfx_events": e["sfx_events"] if e["sfx_events"] is not None else "",
            "contact_sheet": e["contact_sheet"] or "",
            "note": e["note"],
        }
        for key in GATE_KEYS:
            value = e["gate"][key]
            row[f"gate_{key}"] = "" if value is None else int(value)
        rows.append(row)
    return rows


def load_verdicts(path: Path) -> dict:
    """Read docs/gate1/verdicts.yaml; missing file means nothing judged yet."""
    import yaml

    path = Path(path)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
