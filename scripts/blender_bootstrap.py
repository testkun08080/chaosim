"""
Bootstrap script for setting up Blender Python environment.
Run once to verify Blender + dependencies are working.
"""

import subprocess
import sys


def check_blender(blender_path: str = "blender") -> bool:
    try:
        result = subprocess.run(
            [blender_path, "--version"],
            capture_output=True, text=True, timeout=10
        )
        print(result.stdout.strip())
        return result.returncode == 0
    except FileNotFoundError:
        print(f"Blender not found at: {blender_path}")
        return False


def install_pyyaml_in_blender(blender_path: str = "blender"):
    """Install PyYAML into Blender's bundled Python."""
    cmd = [
        blender_path, "--background", "--python-expr",
        "import subprocess, sys; subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyyaml'])"
    ]
    subprocess.run(cmd)


if __name__ == "__main__":
    blender = sys.argv[1] if len(sys.argv) > 1 else "blender"
    if check_blender(blender):
        print("Blender OK. Installing PyYAML...")
        install_pyyaml_in_blender(blender)
        print("Bootstrap complete.")
    else:
        print("Fix Blender path and retry.")
        sys.exit(1)
