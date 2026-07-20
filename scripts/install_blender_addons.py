#!/usr/bin/env python3
"""
Link Chaosim Blender addons into Blender's user scripts/addons folder.

Usage:
  python scripts/install_blender_addons.py
  python scripts/install_blender_addons.py --remove
  BLENDER_PATH=/path/to/blender python scripts/install_blender_addons.py

Each subdirectory of simulators/blender/addons/ becomes a symlink so edits
in the repo are immediately visible in Blender after reload.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ADDONS_SRC = REPO_ROOT / "simulators" / "blender" / "addons"


def get_blender_path() -> str:
    return os.environ.get("BLENDER_PATH", "blender")


def get_blender_version(blender_path: str) -> str:
    result = subprocess.run(
        [blender_path, "--version"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to run Blender at {blender_path}")

    match = re.search(r"Blender\s+(\d+\.\d+)", result.stdout)
    if not match:
        raise RuntimeError(f"Could not parse Blender version:\n{result.stdout}")
    return match.group(1)


def blender_addons_dir(version: str) -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Blender" / version / "scripts" / "addons"
    if sys.platform == "win32":
        return home / "AppData" / "Roaming" / "Blender Foundation" / "Blender" / version / "scripts" / "addons"
    return home / ".config" / "blender" / version / "scripts" / "addons"


def link_addon(src: Path, dest: Path, remove: bool) -> str:
    if remove:
        if dest.is_symlink():
            dest.unlink()
            return f"removed {dest.name}"
        if dest.exists():
            return f"skip {dest.name} (not a symlink)"
        return f"skip {dest.name} (not installed)"

    if dest.is_symlink():
        if dest.resolve() == src.resolve():
            return f"ok {dest.name} (already linked)"
        dest.unlink()
    elif dest.exists():
        return f"error {dest.name} (path exists and is not a symlink)"

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.symlink_to(src, target_is_directory=True)
    return f"linked {dest.name} -> {src}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Chaosim Blender addons via symlink")
    parser.add_argument("--remove", action="store_true", help="Remove symlinks instead of creating them")
    parser.add_argument("--blender", default=get_blender_path(), help="Blender executable path")
    args = parser.parse_args()

    if not ADDONS_SRC.is_dir():
        print(f"Addons source not found: {ADDONS_SRC}")
        return 1

    try:
        version = get_blender_version(args.blender)
    except RuntimeError as exc:
        print(exc)
        print("Set BLENDER_PATH or pass --blender /path/to/blender")
        return 1

    dest_dir = blender_addons_dir(version)
    print(f"Blender {version}")
    print(f"Target: {dest_dir}")

    addon_dirs = sorted(p for p in ADDONS_SRC.iterdir() if p.is_dir() and (p / "__init__.py").is_file())
    if not addon_dirs:
        print("No addons found in simulators/blender/addons/")
        return 1

    for src in addon_dirs:
        dest = dest_dir / src.name
        print(link_addon(src, dest, args.remove))

    action = "Removed" if args.remove else "Installed"
    print(f"\n{action}. Enable in Blender: Edit → Preferences → Add-ons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
