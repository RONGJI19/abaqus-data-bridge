#!/usr/bin/env python3
"""ADB standalone EXE builder.

Usage:
    python build_exe.py          # Build both GUI and CLI
    python build_exe.py --gui    # GUI only
    python build_exe.py --cli    # CLI only

Output: dist/ADB_GUI.exe  and  dist/ADB_CLI.exe
"""

import subprocess
import sys
import shutil
from pathlib import Path


PROJ_ROOT = Path(__file__).parent
DIST = PROJ_ROOT / "dist"
BUILD = PROJ_ROOT / "build"


def check_tool(name: str, install_cmd: str) -> bool:
    """Check if a tool is installed, offer to install if not."""
    try:
        subprocess.run([sys.executable, "-c", f"import {name}"],
                       capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        print(f"[WARN] {name} not found.")
        ans = input(f"  Install now? (pip install {install_cmd}) [Y/n]: ")
        if ans.lower() not in ("n", "no"):
            print(f"  Installing {install_cmd}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", install_cmd])
            return True
        return False


def clean():
    """Remove old build artifacts."""
    for d in (DIST, BUILD):
        if d.exists():
            print(f"  Removing {d}")
            shutil.rmtree(d)


def build(target: str):
    """Run PyInstaller."""
    spec = PROJ_ROOT / "adb_gui.spec"
    if not spec.exists():
        print(f"[ERROR] Spec file not found: {spec}")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(spec),
        "--noconfirm",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
    ]
    print(f"  Running: pyinstaller adb_gui.spec --noconfirm")
    subprocess.check_call(cmd)


def main():
    gui_only = "--gui" in sys.argv
    cli_only = "--cli" in sys.argv

    print()
    print("=" * 50)
    print("  Abaqus Data Bridge — EXE Builder")
    print("=" * 50)
    print()

    # Check prerequisites
    print("[1/4] Checking prerequisites...")
    if gui_only and not check_tool("PySide6", "pyside6"):
        print("[ERROR] PySide6 is required for GUI build.")
        sys.exit(1)
    if not gui_only:
        check_tool("PySide6", "pyside6")  # warn but continue
    check_tool("PyInstaller", "pyinstaller")

    # Clean
    print("[2/4] Cleaning old builds...")
    clean()

    # Build
    print("[3/4] Building...")
    build("gui" if gui_only else "all")

    # Done
    print("[4/4] Done!")
    print()
    print("Output files:")
    for f in DIST.rglob("*.exe"):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f}  ({size_mb:.1f} MB)")
    print()
    print("To distribute: copy the dist/ folder to another computer.")
    print("No Python installation needed on the target machine.")


if __name__ == "__main__":
    main()
